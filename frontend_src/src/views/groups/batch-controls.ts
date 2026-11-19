/**
 * Staged Batch Controls Card (`system_sync` Column 2, `D-050`, `D-055`, `D-064` / `Q6`).
 * - Stages edits in `store.groups.batchDraft` & `Mixed`-safe `store.groups.batchPillDrafts`
 * - Action bar with **Apply to N Devices** (`requestApplyBatchDraft`) + **Reset** (`resetBatchDraft`)
 *   and automatic `Custom` detachment note when grouped Devices are targeted
 */

import {
  renderCard,
  renderHourSelectControl,
  renderRangeControl,
  renderSettingsRow,
} from "../../components/controls.js";
import type { StudioTranslationKey } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type {
  DeviceGroup,
  SharedControlItem,
  SystemDeviceEntry,
} from "../../types.js";
import {
  defaultLocaleTimeFormat,
  entityLabel,
  fmtNumber,
  isValidHexColor,
} from "../../utils/format.js";

const BATCH_CATEGORY_META: ReadonlyArray<{
  id: string;
  labelKey: StudioTranslationKey;
}> = [
  { id: "display", labelKey: "batch.cat_display" },
  { id: "interface", labelKey: "batch.cat_interface" },
  { id: "audio", labelKey: "batch.cat_audio" },
  { id: "power", labelKey: "batch.cat_power" },
  { id: "presence", labelKey: "batch.cat_presence" },
  { id: "security", labelKey: "batch.cat_security" },
];

function renderBatchControlRow(
  store: StudioStore,
  fc: SharedControlItem,
): TemplateResult | typeof nothing {
  const targets = store.groups.filteredControlTargets(fc);
  if (!targets.length) return nothing;

  const eff = store.groups.getEffectiveBatchValue(fc);
  const { value: curState, mixed, staged } = eff;
  const prefKey = fc.pref_key || "";
  const label = prefKey
    ? store.tPrefLabel(prefKey, entityLabel(fc.name))
    : entityLabel(fc.name);
  const secTitle = entityLabel(fc.section_title || fc.section);
  const baseDesc =
    targets.length === 1
      ? store.t("batch.row_meta_one", { section: secTitle })
      : store.t("batch.row_meta_many", {
          section: secTitle,
          count: fmtNumber(targets.length, store.hass, 0),
        });
  const desc = mixed ? `${baseDesc} • ${store.t("batch.mixed_hint")}` : baseDesc;
  const optLabels = fc.option_labels || {};

  const statusBadge = staged
    ? html`<span class="chip chip-primary">${store.t("batch.staged_badge")}</span>`
    : mixed
      ? html`<span class="chip chip-warning">${store.t("batch.mixed_badge")}</span>`
      : nothing;

  let control: TemplateResult;
  if (fc.domain === "select" && fc.options && fc.options.length) {
    const selectValue = mixed && !staged ? "__mixed__" : curState;
    control = html`${statusBadge}
      <select
        aria-label=${label}
        .value=${selectValue}
        @change=${(ev: Event) => {
          const val = (ev.currentTarget as HTMLSelectElement).value;
          if (val !== "__mixed__") {
            store.groups.stageBatchEntityControl(fc, { option: val });
          }
        }}
      >
        ${mixed && !staged
          ? html`<option value="__mixed__" selected disabled>
              ${store.t("batch.mixed_badge")}
            </option>`
          : nothing}
        ${fc.options.map((opt) => {
          const optText =
            optLabels[opt] || (prefKey ? store.tPrefOption(prefKey, opt) : opt);
          return html`<option
            value=${opt}
            ?selected=${!(mixed && !staged) && opt === curState}
          >
            ${optText}
          </option>`;
        })}
      </select>`;
  } else if (fc.domain === "switch") {
    const checked = !mixed && curState === "on";
    control = html`${statusBadge}
      <input
        type="checkbox"
        role="switch"
        aria-label=${label}
        .checked=${checked}
        @change=${(ev: Event) =>
          store.groups.stageBatchEntityControl(fc, {
            action: (ev.currentTarget as HTMLInputElement).checked ? "turn_on" : "turn_off",
          })}
        class="switch"
      />`;
  } else if (fc.domain === "number") {
    const min = fc.min ?? 0;
    const max = fc.max ?? 100;
    const step = fc.step ?? 1;
    const numVal = Number.isFinite(Number(curState)) ? Number(curState) : min;
    control =
      fc.unit === ":00"
        ? html`${statusBadge}
            ${renderHourSelectControl({
              ariaLabel: label,
              value: numVal,
              is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
              hass: store.hass,
              mixed: mixed && !staged,
              mixedLabel: store.t("batch.mixed_badge"),
              onCommit: (raw) => store.groups.stageBatchEntityControl(fc, { level: raw }),
            })}`
        : html`${statusBadge}
            ${renderRangeControl({
              ariaLabel: label,
              value: numVal,
              min,
              max,
              step,
              unit: fc.unit,
              is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
              hass: store.hass,
              onCommit: (raw) => store.groups.stageBatchEntityControl(fc, { level: raw }),
            })}`;
  } else if (fc.domain === "color") {
    const hexVal = isValidHexColor(curState) ? curState.toUpperCase() : "#3898FF";
    control = html`${statusBadge}
      <input
        type="color"
        aria-label=${label}
        .value=${hexVal}
        @change=${(ev: Event) =>
          store.groups.stageBatchColor(fc, (ev.currentTarget as HTMLInputElement).value)}
      />
      <span class="chip">${mixed && !staged ? store.t("batch.mixed_badge") : hexVal}</span>`;
  } else if (fc.domain === "pills" && fc.options && fc.options.length) {
    const pillStates = store.groups.getEffectiveBatchPillStates(fc);
    const hasAnyStaged = pillStates.some((p) => p.staged);
    const hasAnyMixed = pillStates.some((p) => p.state === "mixed");
    const pillBadge = hasAnyStaged
      ? html`<span class="chip chip-primary">${store.t("batch.staged_badge")}</span>`
      : hasAnyMixed
        ? html`<span class="chip chip-warning">${store.t("batch.mixed_badge")}</span>`
        : nothing;

    control = html`<div role="group" aria-label=${label} class="pill-list">
      ${pillBadge}
      ${pillStates.map((pill) => {
        const isOn = pill.state === "on";
        const isMixed = pill.state === "mixed";
        const pillText = isMixed
          ? store.t("batch.mixed_pill_suffix", { label: pill.label })
          : pill.label;
        return html`<span class="pill ${isOn ? "enabled" : ""}">
          <button
            type="button"
            aria-pressed=${isMixed ? "mixed" : isOn ? "true" : "false"}
            @click=${() => store.groups.stageBatchPillToggle(fc, pill.token)}
            class="pill-toggle"
          >
            ${pillText}
          </button>
        </span>`;
      })}
    </div>`;
  } else {
    control = html`${statusBadge}
      <span class="chip">${mixed ? store.t("batch.mixed_badge") : curState}</span>`;
  }

  return renderSettingsRow({
    label,
    description: desc,
    stacked: fc.domain === "pills",
    control,
  });
}

function requestBatchListPush(
  store: StudioStore,
  sourceSubentryId: string,
  latterDevices: readonly SystemDeviceEntry[],
  matchingCount: number,
  selectedTargetName: string,
  copyKeys: string[],
  listLabel: string,
): void {
  if (matchingCount <= 1) {
    void store.groups.applyBatchCopyFromDevice(sourceSubentryId, copyKeys);
    return;
  }
  const srcDev = latterDevices.find((d) => d.subentry_id === sourceSubentryId);
  const devTitle = srcDev?.title || sourceSubentryId;
  store.openConfirm({
    kind: "batch_copy_list",
    title: store.t("batch.confirm_push_list_title", {
      listLabel,
      target: selectedTargetName,
    }),
    consequence: store.t("batch.confirm_push_list_body", {
      listLabel,
      device: devTitle,
    }),
    confirmLabel: store.t("batch.confirm_push_list_confirm"),
    danger: false,
    blastRadiusCount: matchingCount,
    onConfirm: async () => {
      await store.groups.applyBatchCopyFromDevice(sourceSubentryId, copyKeys);
    },
  });
}

export function renderBatchControlsCard(
  store: StudioStore,
  groups: readonly DeviceGroup[],
  latterDevices: readonly SystemDeviceEntry[],
  systemControls: readonly SharedControlItem[],
): TemplateResult {
  const validTargetFilters = new Set<string>([
    "all",
    "online",
    "roaming",
    "stationary",
    "group:custom",
    ...groups.map((g) => `group:${g.id}`),
  ]);
  const activeFilter = validTargetFilters.has(store.batchTargetFilter || "all")
    ? store.batchTargetFilter || "all"
    : "all";
  const activeCat = store.batchCategoryFilter || "all";

  const selectedTargetName =
    activeFilter === "all"
      ? store.t("batch.all_latter_devices")
      : activeFilter === "online"
        ? store.t("batch.online_devices")
        : activeFilter === "roaming"
          ? store.t("batch.roaming_devices")
          : activeFilter === "stationary"
            ? store.t("batch.stationary_devices")
            : activeFilter === "group:custom"
              ? store.t("common.custom")
              : groups.find((g) => `group:${g.id}` === activeFilter)?.name ||
                activeFilter.replace(/^group:/, "");

  const matchingDevs = store.groups.matchingBatchDevices();
  const batchCopySrc =
    store.batchCopySourceSubentryId ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";

  const draftCount = store.groups.batchDraftCount;
  const hasDraft = store.groups.hasBatchDraft;
  const detachCount = store.groups.previewBatchDetachmentCount();
  const applyLabel =
    matchingDevs.length === 1
      ? store.t("batch.apply_to_one")
      : store.t("batch.apply_to_n", { count: fmtNumber(matchingDevs.length, store.hass, 0) });

  const renderBatchCopyListsSection = (): TemplateResult | typeof nothing => {
    if (!latterDevices.length || !matchingDevs.some((d) => d.has_display !== false)) {
      return nothing;
    }
    return html`<div class="settings-list">
      <div class="subsection-title">${store.t("batch.copy_lists_title")}</div>
      ${renderSettingsRow({
        label: store.t("batch.template_device"),
        description: store.t("batch.template_device_desc", { target: selectedTargetName }),
        control: html`<select
          id="batch-copy-source"
          aria-label=${store.t("batch.template_device_aria")}
          .value=${batchCopySrc}
          @change=${(ev: Event) => {
            store.batchCopySourceSubentryId = (ev.currentTarget as HTMLSelectElement).value;
            store.host.requestUpdate();
          }}
        >
          ${latterDevices.map(
            (d) =>
              html`<option value=${d.subentry_id} ?selected=${d.subentry_id === batchCopySrc}>
                ${d.title}
              </option>`,
          )}
        </select>`,
      })}
      <div class="input-action-row">
        <button
          type="button"
          @click=${() =>
            requestBatchListPush(
              store,
              batchCopySrc,
              latterDevices,
              matchingDevs.length,
              selectedTargetName,
              ["dock_items"],
              store.t("card.app_dock"),
            )}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("batch.push_dock")}
        </button>
        <button
          type="button"
          @click=${() =>
            requestBatchListPush(
              store,
              batchCopySrc,
              latterDevices,
              matchingDevs.length,
              selectedTargetName,
              ["pinned_items"],
              store.t("dialogs.pinned_label"),
            )}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("batch.push_pinned")}
        </button>
        <button
          type="button"
          @click=${() =>
            requestBatchListPush(
              store,
              batchCopySrc,
              latterDevices,
              matchingDevs.length,
              selectedTargetName,
              ["world_clocks"],
              store.t("dialogs.world_clocks_label"),
            )}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("batch.push_clocks")}
        </button>
      </div>
    </div>`;
  };

  return renderCard({
    id: "card-batch-controls",
    title: store.t("batch.title"),
    subtitle: store.t("batch.subtitle"),
    headerActions: html`${hasDraft
        ? html`<span class="chip chip-primary">
            ${store.t("batch.staged_count", { count: fmtNumber(draftCount, store.hass, 0) })}
          </span>`
        : nothing}
      <select
        id="batch-target-filter"
        aria-label=${store.t("batch.target_filter_aria")}
        .value=${activeFilter}
        @change=${(ev: Event) =>
          store.groups.setBatchTargetFilter((ev.currentTarget as HTMLSelectElement).value || "all")}
      >
        <option value="all" ?selected=${activeFilter === "all"}>
          ${store.t("batch.all_latter_devices")}
        </option>
        <option value="online" ?selected=${activeFilter === "online"}>
          ${store.t("batch.online_devices")}
        </option>
        <option value="roaming" ?selected=${activeFilter === "roaming"}>
          ${store.t("batch.roaming_devices")}
        </option>
        <option value="stationary" ?selected=${activeFilter === "stationary"}>
          ${store.t("batch.stationary_devices")}
        </option>
        ${groups.map(
          (g) =>
            html`<option
              value=${`group:${g.id}`}
              ?selected=${activeFilter === `group:${g.id}`}
            >
              ${g.name}
            </option>`,
        )}
        <option value="group:custom" ?selected=${activeFilter === "group:custom"}>
          ${store.t("common.custom")}
        </option>
      </select>
      <select
        id="batch-cat-filter"
        aria-label=${store.t("batch.category_filter_aria")}
        .value=${activeCat}
        @change=${(ev: Event) => {
          store.batchCategoryFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
          store.host.requestUpdate();
        }}
      >
        <option value="all" ?selected=${activeCat === "all"}>
          ${store.t("batch.all_categories")}
        </option>
        ${BATCH_CATEGORY_META.map(
          (cat) =>
            html`<option value=${cat.id} ?selected=${activeCat === cat.id}>
              ${store.t(cat.labelKey)}
            </option>`,
        )}
      </select>`,
    contentClass: "stack",
    body: !matchingDevs.length
      ? html`<p class="empty-state">
          ${activeFilter === "all"
            ? store.t("batch.empty_all")
            : store.t("batch.empty_target", { target: selectedTargetName })}
        </p>`
      : html`<div class="help-text">
            ${store.t("batch.target_summary", {
              count: fmtNumber(matchingDevs.length, store.hass, 0),
              names: matchingDevs.map((d) => d.title).join(", "),
            })}
          </div>

          ${hasDraft && detachCount > 0
            ? html`<div role="status" class="alert alert-warning">
                <div class="alert-body">
                  <span>
                    ${detachCount === 1
                      ? store.t("batch.detachment_note_one")
                      : store.t("batch.detachment_note_many", {
                          count: fmtNumber(detachCount, store.hass, 0),
                        })}
                  </span>
                </div>
              </div>`
            : nothing}

          <div id="system-controls-list" class="stack">
            ${activeCat === "all"
              ? BATCH_CATEGORY_META.map((cat) => {
                  const rows = systemControls
                    .filter((fc) => fc.section === cat.id)
                    .map((fc) => renderBatchControlRow(store, fc))
                    .filter((row) => row !== nothing);
                  const copyBlock =
                    cat.id === "interface" ? renderBatchCopyListsSection() : nothing;
                  if (!rows.length && copyBlock === nothing) return nothing;
                  return html`<details
                    ?open=${store.openBatchCategories.has(cat.id)}
                    @toggle=${(ev: Event) => {
                      if (ev.target !== ev.currentTarget) return;
                      const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
                      if (isOpen) store.openBatchCategories.add(cat.id);
                      else store.openBatchCategories.delete(cat.id);
                    }}
                    class="sub-collapsible"
                  >
                    <summary>${store.t(cat.labelKey)}</summary>
                    <div class="card-content stack">
                      ${rows.length ? html`<div class="settings-list">${rows}</div>` : nothing}
                      ${copyBlock}
                    </div>
                  </details>`;
                })
              : (() => {
                  const rows = systemControls
                    .filter((fc) => fc.section === activeCat)
                    .map((fc) => renderBatchControlRow(store, fc))
                    .filter((row) => row !== nothing);
                  const copyBlock =
                    activeCat === "interface" ? renderBatchCopyListsSection() : nothing;
                  if (!rows.length && copyBlock === nothing) {
                    return html`<p class="empty-state">${store.t("batch.empty_category")}</p>`;
                  }
                  return html`${rows.length
                    ? html`<div class="settings-list">${rows}</div>`
                    : nothing}
                  ${copyBlock}`;
                })()}
          </div>`,
    footerActions: matchingDevs.length
      ? html`<button
            type="button"
            id="btn-batch-reset"
            ?disabled=${!hasDraft || store.groups.batchBusy}
            @click=${() => store.groups.resetBatchDraft()}
            class="btn btn-secondary"
          >
            ${store.t("batch.reset_staged")}
          </button>
          <button
            type="button"
            id="btn-batch-apply"
            ?disabled=${!hasDraft || store.groups.batchBusy}
            @click=${() => store.groups.requestApplyBatchDraft()}
            class="btn btn-primary"
          >
            ${applyLabel}
          </button>`
      : nothing,
  });
}
