/**
 * World Clocks & Time App Configuration Helpers (`#latter-app-config-modal` `time`, `D-038`, `D-039`, `D-064`).
 * - Sortable World Clocks list via `renderSortableList` (`≡` drag handle + focus-preserving `↑`/`↓`)
 * - `focusSafe` text bindings so live WS pushes never clobber typing
 */

import { MAX_WORLD_CLOCKS, WORLD_CLOCK_ZONES_CATALOG } from "../../constants.js";
import {
  isValidWorldClockZone,
  parseWorldClocksSpec,
  sanitizeClockLabel,
  serializeWorldClocksSpec,
  type WorldClockItemView,
} from "../../domain/world-clocks.js";
import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import { defaultLocaleTimeFormat } from "../../utils/format.js";
import {
  renderSelectRow,
  renderSettingsRow,
  renderSortableList,
  renderSwitchRow,
  renderTrashIconButton,
} from "../controls.js";

export {
  parseWorldClocksSpec,
  sanitizeClockLabel,
  serializeWorldClocksSpec,
  type WorldClockItemView,
};

const TEXT_INPUT_DEBOUNCE_MS = 600;

function isImeSafeEnter(ev: KeyboardEvent): boolean {
  return ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229;
}

export function renderTimeAppConfigBody(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const zonesCatalog = data?.world_clock_zones?.length
    ? data.world_clock_zones
    : WORLD_CLOCK_ZONES_CATALOG;
  const knownZoneSet = new Set(zonesCatalog.map((z) => z.iana));

  const localClockLabelPref = store.entity.getPref("local_clock_label");
  const localClockLabelValue = sanitizeClockLabel(
    localClockLabelPref?.value ?? cfg.local_clock_label ?? "",
  );
  const showUtcClockPref = store.entity.getPref("show_utc_clock");
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);
  const worldClocksPref = store.entity.getPref("world_clocks");
  const enabledWorldClocks = parseWorldClocksSpec(
    worldClocksPref?.value ?? cfg.world_clocks ?? "",
  );
  const atWorldClockLimit = enabledWorldClocks.length >= MAX_WORLD_CLOCKS;

  while (store.worldClockRowKeys.length < enabledWorldClocks.length) {
    store.worldClockRowSeq += 1;
    store.worldClockRowKeys.push(`wc-${store.worldClockRowSeq}`);
  }
  if (store.worldClockRowKeys.length > enabledWorldClocks.length) {
    store.worldClockRowKeys.length = enabledWorldClocks.length;
  }

  const renderWorldClockZoneOptions = (selectedIana: string): TemplateResult => {
    const missingSelected =
      selectedIana && !knownZoneSet.has(selectedIana)
        ? html`<option value=${selectedIana} selected>${selectedIana}</option>`
        : nothing;
    return html`${missingSelected}${zonesCatalog.map(
      (z) =>
        html`<option value=${z.iana} ?selected=${z.iana === selectedIana}>${z.label}</option>`,
    )}`;
  };

  const updateWorldClocks = (
    nextItems: WorldClockItemView[],
    focusId?: string,
    debounceMs?: number,
  ): void => {
    store.entity.stageDeviceSetting(
      "world_clocks",
      serializeWorldClocksSpec(nextItems),
      focusId,
      debounceMs,
    );
  };

  const updateWorldClockItem = (
    idx: number,
    patch: Partial<WorldClockItemView>,
    focusId?: string,
    debounceMs?: number,
    trimLabel = true,
  ): void => {
    if (idx < 0 || idx >= enabledWorldClocks.length) return;
    const prev = enabledWorldClocks[idx];
    if (!prev) return;
    const nextIana = (patch.iana ?? prev.iana).trim();
    if (!isValidWorldClockZone(nextIana)) {
      return;
    }
    const nextLabel =
      patch.label !== undefined
        ? sanitizeClockLabel(patch.label, 32, trimLabel)
        : prev.label;
    if (!nextLabel.trim()) return;
    const dup = enabledWorldClocks.some(
      (item, i) =>
        i !== idx &&
        item.iana === nextIana &&
        item.label.toLowerCase() === nextLabel.trim().toLowerCase(),
    );
    if (dup) return;
    const next = enabledWorldClocks.map((item, i) =>
      i === idx ? { label: nextLabel.trim(), iana: nextIana } : { ...item },
    );
    updateWorldClocks(next, focusId, debounceMs);
  };

  const reorderWorldClocks = (fromIdx: number, toIdx: number): void => {
    if (
      fromIdx < 0 ||
      toIdx < 0 ||
      fromIdx >= enabledWorldClocks.length ||
      toIdx >= enabledWorldClocks.length ||
      fromIdx === toIdx
    ) {
      return;
    }
    const next = [...enabledWorldClocks];
    const [picked] = next.splice(fromIdx, 1);
    if (!picked) return;
    next.splice(toIdx, 0, picked);
    if (store.worldClockRowKeys.length === enabledWorldClocks.length) {
      const [pickedKey] = store.worldClockRowKeys.splice(fromIdx, 1);
      if (pickedKey !== undefined) {
        store.worldClockRowKeys.splice(toIdx, 0, pickedKey);
      }
    }
    updateWorldClocks(next);
  };

  const removeWorldClock = (idx: number): void => {
    if (idx >= 0 && idx < store.worldClockRowKeys.length) {
      store.worldClockRowKeys.splice(idx, 1);
    }
    updateWorldClocks(enabledWorldClocks.filter((_, i) => i !== idx));
  };

  const getRenderRoot = (): ShadowRoot | null =>
    (store.host as unknown as { renderRoot?: ShadowRoot })?.renderRoot ?? null;

  const onAddWorldClock = (): void => {
    if (atWorldClockLimit) return;
    const root = getRenderRoot();
    const newLabelEl = root?.getElementById(
      "cfg-world_clock_new_label",
    ) as HTMLInputElement | null;
    const zoneSelEl = root?.getElementById(
      "cfg-world_clocks_add",
    ) as HTMLSelectElement | null;
    const typedLabel = sanitizeClockLabel(newLabelEl?.value ?? store.worldClockNewLabel);
    const picked = (zoneSelEl?.value ?? store.worldClockNewZone).trim();
    if (!typedLabel) {
      store.showToast(store.t("dialogs.toast_enter_city"), true);
      newLabelEl?.focus();
      return;
    }
    if (!isValidWorldClockZone(picked)) {
      store.showToast(store.t("dialogs.toast_select_tz"), true);
      zoneSelEl?.focus();
      return;
    }
    const dup = enabledWorldClocks.some(
      (item) =>
        item.iana === picked && item.label.toLowerCase() === typedLabel.toLowerCase(),
    );
    if (dup) {
      store.showToast(store.t("dialogs.toast_dup_world_clock"), true);
      return;
    }
    store.worldClockNewLabel = "";
    store.worldClockNewZone = "";
    if (newLabelEl) newLabelEl.value = "";
    if (zoneSelEl) zoneSelEl.value = "";
    store.worldClockRowSeq += 1;
    store.worldClockRowKeys.push(`wc-${store.worldClockRowSeq}`);
    updateWorldClocks(
      [...enabledWorldClocks, { label: typedLabel, iana: picked }],
      "btn-world_clock_add",
    );
  };

  const timeFormatPref = store.entity.getPref("time_format");
  const timeFormatSpec = store.entity.getPrefSpec("time_format");
  const rawTimeFormatOpts =
    timeFormatPref?.options && timeFormatPref.options.length > 0
      ? timeFormatPref.options
      : timeFormatSpec?.options || [];
  const rawTimeFormatCandidate = timeFormatPref?.value ?? cfg.time_format;
  const resolvedTimeFormat =
    rawTimeFormatCandidate !== undefined &&
    rawTimeFormatCandidate !== null &&
    String(rawTimeFormatCandidate).trim() !== ""
      ? String(rawTimeFormatCandidate)
      : defaultLocaleTimeFormat(store.hass);

  return html`<div class="settings-list">
    ${rawTimeFormatOpts.length > 0
      ? renderSelectRow({
          id: "cfg-time_format",
          label: store.tPrefLabel("time_format"),
          description: store.t("dev_interface.time_format_desc"),
          value: rawTimeFormatOpts.includes(resolvedTimeFormat)
            ? resolvedTimeFormat
            : rawTimeFormatOpts[0],
          rawOptions: rawTimeFormatOpts.map((opt) => ({
            value: opt,
            label: store.tPrefOption("time_format", opt),
          })),
          onChange: (val) =>
            store.entity.stageDeviceSetting("time_format", val, "cfg-time_format"),
        })
      : nothing}
    ${renderSettingsRow({
      id: "time-local-clock-label",
      label: store.t("dialogs.local_clock_label"),
      forId: "cfg-local_clock_label",
      description: store.t("dialogs.local_clock_desc"),
      control: html`<input
        type="text"
        id="cfg-local_clock_label"
        maxlength="32"
        enterkeyhint="done"
        placeholder=${store.t("dialogs.optional_label_placeholder")}
        .value=${focusSafe(localClockLabelValue)}
        @input=${(ev: Event) => {
          const liveVal = sanitizeClockLabel(
            (ev.currentTarget as HTMLInputElement).value,
            32,
            false,
          );
          store.entity.stageDeviceSetting(
            "local_clock_label",
            liveVal,
            "cfg-local_clock_label",
            TEXT_INPUT_DEBOUNCE_MS,
          );
        }}
        @change=${(ev: Event) => {
          const el = ev.currentTarget as HTMLInputElement;
          const cleaned = sanitizeClockLabel(el.value);
          el.value = cleaned;
          store.entity.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
        }}
        @keydown=${(ev: KeyboardEvent) => {
          if (!isImeSafeEnter(ev)) return;
          ev.preventDefault();
          const el = ev.currentTarget as HTMLInputElement;
          const cleaned = sanitizeClockLabel(el.value);
          el.value = cleaned;
          store.entity.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
          void store.entity.flushAllPendingSettings();
        }}
      />`,
    })}
    ${renderSwitchRow({
      id: "cfg-show_utc_clock",
      label: store.t("dialogs.show_utc_label"),
      description: store.t("dialogs.show_utc_desc"),
      checked: showUtcClock,
      onChange: (checked) => {
        store.entity.stageDeviceSetting("show_utc_clock", checked, "cfg-show_utc_clock");
      },
    })}
    ${renderSettingsRow({
      id: "time-world-clocks",
      label: store.t("dialogs.world_clocks_label"),
      description: store.t("dialogs.world_clocks_desc"),
      stacked: true,
      control: html`<div class="stack">
        ${enabledWorldClocks.length > 0
          ? renderSortableList({
              id: "world-clocks-list",
              ariaLabel: store.t("dialogs.world_clocks_aria"),
              items: enabledWorldClocks,
              getKey: (_entry, idx) => store.worldClockRowKeys[idx] || `wc-row-${idx}`,
              getLabel: (entry) => entry.label,
              onReorder: reorderWorldClocks,
              overlay: store.localeOverlay,
              renderContent: (entry, idx) => {
                const lblId = `cfg-world_clock_${idx + 1}_label`;
                const zoneId = `cfg-world_clock_${idx + 1}_zone`;
                return html`<div class="list-row-main">
                  <div class="stacked-field">
                    <label for=${lblId}>
                      ${store.t("dialogs.world_clock_city_label", { index: idx + 1 })}
                    </label>
                    <input
                      type="text"
                      id=${lblId}
                      maxlength="32"
                      enterkeyhint="done"
                      placeholder=${store.t("dialogs.city_label_placeholder")}
                      .value=${focusSafe(entry.label)}
                      @input=${(ev: Event) => {
                        const liveVal = sanitizeClockLabel(
                          (ev.currentTarget as HTMLInputElement).value,
                          32,
                          false,
                        );
                        if (liveVal.trim()) {
                          updateWorldClockItem(
                            idx,
                            { label: liveVal },
                            lblId,
                            TEXT_INPUT_DEBOUNCE_MS,
                            false,
                          );
                        }
                      }}
                      @change=${(ev: Event) => {
                        const el = ev.currentTarget as HTMLInputElement;
                        const cleaned = sanitizeClockLabel(el.value);
                        if (!cleaned) {
                          el.value = entry.label;
                          store.showToast(store.t("dialogs.toast_city_empty"), true);
                          return;
                        }
                        el.value = cleaned;
                        updateWorldClockItem(idx, { label: cleaned }, lblId);
                      }}
                      @keydown=${(ev: KeyboardEvent) => {
                        if (!isImeSafeEnter(ev)) return;
                        ev.preventDefault();
                        const el = ev.currentTarget as HTMLInputElement;
                        const cleaned = sanitizeClockLabel(el.value);
                        if (!cleaned) {
                          el.value = entry.label;
                          store.showToast(store.t("dialogs.toast_city_empty"), true);
                          return;
                        }
                        el.value = cleaned;
                        updateWorldClockItem(idx, { label: cleaned }, lblId);
                        void store.entity.flushAllPendingSettings();
                      }}
                    />
                  </div>
                  <div class="stacked-field">
                    <label for=${zoneId}>
                      ${store.t("dialogs.world_clock_zone_label", { index: idx + 1 })}
                    </label>
                    <select
                      id=${zoneId}
                      .value=${entry.iana}
                      @change=${(ev: Event) =>
                        updateWorldClockItem(
                          idx,
                          { iana: (ev.currentTarget as HTMLSelectElement).value },
                          zoneId,
                        )}
                    >
                      ${renderWorldClockZoneOptions(entry.iana)}
                    </select>
                  </div>
                </div>`;
              },
              renderActions: (entry, idx) =>
                renderTrashIconButton(
                  store.t("action.remove_item", {
                    item: `${entry.label} (${entry.iana})`,
                  }),
                  () => removeWorldClock(idx),
                ),
            })
          : nothing}
        <div class="list-row">
          <div class="list-row-main">
            <div class="stacked-field">
              <label for="cfg-world_clock_new_label">
                ${store.t("dialogs.new_city_label")}
              </label>
              <input
                type="text"
                id="cfg-world_clock_new_label"
                maxlength="32"
                enterkeyhint="done"
                placeholder=${store.t("dialogs.city_label_placeholder")}
                ?disabled=${atWorldClockLimit}
                .value=${focusSafe(store.worldClockNewLabel)}
                @input=${(ev: Event) => {
                  store.worldClockNewLabel = (ev.currentTarget as HTMLInputElement).value;
                  store.host.requestUpdate();
                }}
                @keydown=${(ev: KeyboardEvent) => {
                  if (!isImeSafeEnter(ev)) return;
                  ev.preventDefault();
                  onAddWorldClock();
                }}
              />
            </div>
            <div class="stacked-field">
              <label for="cfg-world_clocks_add">${store.t("dialogs.add_time_zone")}</label>
              <select
                id="cfg-world_clocks_add"
                ?disabled=${atWorldClockLimit}
                .value=${store.worldClockNewZone}
                @change=${(ev: Event) => {
                  store.worldClockNewZone = (ev.currentTarget as HTMLSelectElement).value;
                  store.host.requestUpdate();
                }}
              >
                <option value="" ?selected=${!store.worldClockNewZone}>
                  ${atWorldClockLimit
                    ? store.t("dialogs.max_world_clocks")
                    : store.t("dialogs.select_tz_placeholder")}
                </option>
                ${atWorldClockLimit
                  ? nothing
                  : renderWorldClockZoneOptions(store.worldClockNewZone)}
              </select>
            </div>
          </div>
          <button
            type="button"
            id="btn-world_clock_add"
            ?disabled=${atWorldClockLimit}
            @click=${() => onAddWorldClock()}
            class="btn btn-primary"
          >
            ${store.t("action.add")}
          </button>
        </div>
      </div>`,
    })}
  </div>`;
}
