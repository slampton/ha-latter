/**
 * System Media & Remotes View (`remotes`): Remote Controls, Volume Overrides, Remote Groups & Device Assignments.
 */

import { renderSelectOptions, renderTrashIconButton } from "../components/controls.js";
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

  const speakerChoices = cat.ma_speakers || cat.speakers || [];
  const targetChoices = cat.volume_targets || cat.remotes || [];
  const inventoryIds = remotes.filter(Boolean);

  const friendlyRemoteLabel = (entId: string): string => {
    const found = (cat.remotes || []).find((r) => r.id === entId);
    return found ? found.name.split(" (")[0] : entId;
  };

  return html`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Remote Controls</h3>
              <p class="card-subtitle">
                Up to 10 TV, streamer, or receiver entities controlled from the Remote screen.
              </p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.addStringListRow("remotes_list", "", 10)}
                class="btn btn-secondary btn-compact"
              >
                Add Remote
              </button>
            </div>
          </div>
          <div id="remotes-list" class="card-content stack">
            ${remotes.length
              ? remotes.map(
                  (remId, idx) => html`<div class="list-row remote-row-item">
                    <div class="stacked-field list-row-grow">
                      <span class="field-label rem-slot-lbl">
                        ${idx === 0 ? "Slot 1 (Primary Power Target)" : `Slot ${idx + 1}`}
                      </span>
                      <select
                        aria-label="Remote or media player"
                        .value=${remId}
                        @change=${(ev: Event) =>
                          store.updateStringListRow(
                            "remotes_list",
                            idx,
                            (ev.currentTarget as HTMLSelectElement).value,
                          )}
                        class="rem-ent-sel"
                      >
                        ${renderSelectOptions(
                          cat.remotes,
                          remId,
                          "— Choose a remote or media player —",
                        )}
                      </select>
                    </div>
                    ${renderTrashIconButton("Remove remote", () =>
                      store.removeStringListRow("remotes_list", idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">No remote controls configured yet.</p>`}
          </div>
        </div>

        <div id="card-volume-overrides" class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Speaker Volume Overrides</h3>
              <p class="card-subtitle">
                Redirects volume buttons when audio plays through an external AVR or soundbar.
              </p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.addVolumeOverrideRow()}
                class="btn btn-secondary btn-compact"
              >
                Add Override
              </button>
            </div>
          </div>
          <div id="volume-overrides-list" class="card-content stack">
            ${volOverrides.length
              ? volOverrides.map(
                  (vo, idx) => html`<div class="list-row vol-override-row">
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
                          class="vo-spk"
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
                          class="vo-tgt"
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
          </div>
        </div>
      </div>

      <div class="column">
        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Remote Control Groups</h3>
              <p class="card-subtitle">
                Bind sets of remotes to Home Assistant Areas or specific Devices.
              </p>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.addRemoteGroupRow()}
                class="btn btn-secondary btn-compact"
              >
                Add Group
              </button>
            </div>
          </div>
          <div id="remote-groups-list" class="card-content stack">
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
                              const badge = isEn ? (pos === 0 ? "★ Primary: " : `#${pos + 1}: `) : "+ ";
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
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Device Assignments</h3>
          </div>
          <div id="device-remote-assignments-list" class="card-content settings-list">
            ${screenDevs.length
              ? screenDevs.map((d) => {
                  const curMode = d.device_remote_group || "area_auto";
                  return html`<div class="settings-row">
                    <div class="settings-row-text">
                      <span class="row-label">${d.title}</span>
                      <p class="row-description">Active Area: ${d.active_area_name || "—"}</p>
                    </div>
                    <div class="settings-row-control">
                      <select
                        aria-label=${`Remotes for ${d.title}`}
                        .value=${curMode}
                        @change=${(ev: Event) =>
                          void store.assignDeviceRemoteGroup(
                            d.subentry_id,
                            (ev.currentTarget as HTMLSelectElement).value,
                          )}
                      >
                        <option value="area_auto" ?selected=${curMode === "area_auto"}>
                          Follow the active Area
                        </option>
                        ${remoteGroups.map(
                          (g) =>
                            html`<option
                              value=${`group:${g.id}`}
                              ?selected=${curMode === `group:${g.id}`}
                            >
                              Group: ${g.name}
                            </option>`,
                        )}
                        <option value="all" ?selected=${curMode === "all"}>
                          All System remotes
                        </option>
                      </select>
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No Devices with a screen yet.</p>`}
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
