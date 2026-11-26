/**
 * Entity Slot Lists, Native/Pref Control Row Adapters, & Quick Action Button Grid
 * (`components/controls/entity-adapters.ts`, `D-061`, `D-062`).
 */

import { t, tPrefLabel, tPrefOption } from "../../i18n/index.js";
import { focusSafe, html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { CatalogChoice, DevicePrefItem, EspHomeEntityItem } from "../../types.js";
import { compareLocaleText, entityLabel, fmtNumber } from "../../utils/format.js";
import {
  isDeviceTime24h,
  renderSelectOptions,
  renderTrashIconButton,
} from "./aria-helpers.js";
import {
  renderHourSelectRow,
  renderRangeControl,
  renderSettingsRow,
} from "./rows.js";
import { renderSortableList } from "./sortable-lists.js";

export interface EntitySlotListOptions {
  id: string;
  items: readonly string[];
  choices: readonly CatalogChoice[] | undefined;
  emptyOptionLabel: string;
  emptyStateText: string;
  selectAriaLabel: string;
  removeAriaLabel: string;
  slotLabel?: (idx: number) => string;
  slotMeta?: (item: string, idx: number) => TemplateResult | typeof nothing;
  extraActions?: (item: string, idx: number) => TemplateResult | typeof nothing;
  stacked?: boolean;
  onReorder?: (fromIndex: number, toIndex: number) => void;
  onChange: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

export function renderEntitySlotList(opts: EntitySlotListOptions): TemplateResult {
  if (!opts.items.length) {
    return html`<div id=${opts.id} class="stack">
      <p class="empty-state">${opts.emptyStateText}</p>
    </div>`;
  }

  const renderSlotField = (val: string, idx: number, includeLabel = true): TemplateResult => html`<div
    class="stacked-field list-row-grow"
  >
    ${includeLabel && opts.slotLabel
      ? html`<span class="field-label">${opts.slotLabel(idx)}</span>`
      : nothing}
    <select
      aria-label=${opts.selectAriaLabel}
      .value=${live(val)}
      @change=${(ev: Event) =>
        opts.onChange(idx, (ev.currentTarget as HTMLSelectElement).value)}
    >
      ${renderSelectOptions(opts.choices, val, opts.emptyOptionLabel)}
    </select>
    ${opts.slotMeta ? opts.slotMeta(val, idx) : nothing}
  </div>`;

  if (opts.onReorder) {
    return renderSortableList({
      id: opts.id,
      items: opts.items,
      getKey: (val) => (val ? `ent:${val}` : "empty"),
      getLabel: (val, idx) =>
        opts.slotLabel ? opts.slotLabel(idx) : val || `${opts.selectAriaLabel} ${idx + 1}`,
      onReorder: opts.onReorder,
      renderHeader: opts.stacked
        ? (_val, idx) =>
            opts.slotLabel
              ? html`<span class="field-label">${opts.slotLabel(idx)}</span>`
              : nothing
        : undefined,
      renderContent: (val, idx) => renderSlotField(val, idx, !opts.stacked),
      renderActions: (val, idx) => html`
        ${opts.extraActions ? opts.extraActions(val, idx) : nothing}
        ${renderTrashIconButton(opts.removeAriaLabel, () => opts.onRemove(idx))}
      `,
    });
  }

  return html`<div id=${opts.id} class="stack">
    ${opts.items.map(
      (val, idx) => html`<div class="list-row">
        ${renderSlotField(val, idx)}
        ${opts.extraActions ? opts.extraActions(val, idx) : nothing}
        ${renderTrashIconButton(opts.removeAriaLabel, () => opts.onRemove(idx))}
      </div>`,
    )}
  </div>`;
}

function getLocaleOverlay(store: StudioStore): Readonly<Record<string, string>> | null {
  const stateAny = store.state as Record<string, unknown> | null | undefined;
  const overlay = stateAny?.locale_strings;
  return overlay && typeof overlay === "object"
    ? (overlay as Readonly<Record<string, string>>)
    : null;
}

export function renderNativeControlRow(store: StudioStore, item: EspHomeEntityItem): TemplateResult {
  const overlay = getLocaleOverlay(store);
  const prefKey = item.pref_key || "";
  const label = prefKey
    ? tPrefLabel(prefKey, entityLabel(item.name || item.entity_id), overlay)
    : entityLabel(item.name || item.entity_id);
  const dom = item.domain;
  const st = String(item.state ?? "");
  const unavailable = !prefKey && (st === "unavailable" || st === "unknown");

  if (dom === "switch") {
    const isOn = st === "on";
    const onToggle = (ev: Event): void => {
      const checked = (ev.currentTarget as HTMLInputElement).checked;
      if (prefKey) {
        store.entity.stageDeviceSetting(prefKey, checked);
      } else {
        void store.entity.espAction(
          item.entity_id,
          checked ? "turn_on" : "turn_off",
          checked ? "on" : "off",
        );
      }
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        ?disabled=${unavailable}
        .checked=${live(isOn)}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }

  if (dom === "select") {
    const opts = item.options || [];
    const onChange = (ev: Event): void => {
      const nextVal = (ev.currentTarget as HTMLSelectElement).value;
      if (prefKey) {
        store.entity.stageDeviceSetting(prefKey, nextVal);
      } else {
        void store.entity.espSelect(item.entity_id, nextVal);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${live(st)} @change=${onChange}>
        ${opts.map(
          (opt) =>
            html`<option value=${opt} .selected=${live(opt === st)}>
              ${tPrefOption(prefKey, opt, overlay)}
            </option>`,
        )}
      </select>`,
    });
  }

  if (dom === "number") {
    const min = item.min ?? 0;
    const max = item.max ?? 100;
    const step = item.step ?? 1;
    const numVal = Number.isFinite(Number(st)) ? Number(st) : min;
    const commitNumber = (raw: number): void => {
      if (prefKey) {
        store.entity.stageDeviceSetting(prefKey, raw);
      } else {
        void store.entity.espNumber(item.entity_id, raw);
      }
    };
    if (max - min <= 250 && item.mode !== "box") {
      return renderSettingsRow({
        label,
        control: renderRangeControl({
          ariaLabel: label,
          value: numVal,
          min,
          max,
          step,
          unit: item.unit,
          is24h: isDeviceTime24h(store),
          disabled: unavailable,
          hass: store.hass,
          onCommit: commitNumber,
        }),
      });
    }
    return renderSettingsRow({
      label,
      control: html`<input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          ?disabled=${unavailable}
          .value=${focusSafe(String(numVal))}
          @change=${(ev: Event) => {
            const raw = Number((ev.currentTarget as HTMLInputElement).value);
            if (Number.isFinite(raw)) commitNumber(raw);
          }}
        />
        ${item.unit ? html`<span class="help-text">${item.unit}</span>` : nothing}`,
    });
  }

  if (dom === "button") {
    const buttonUnavailable = st === "unavailable";
    const toastMsg = label.toLowerCase().includes("restart")
      ? t("sync.restarting_device", undefined, overlay)
      : t("sync.triggered_action", { label }, overlay);
    const onRun = (): void => {
      if (item.device_command) {
        void store.entity.runDeviceAction(item.device_command, toastMsg);
      } else {
        void store.entity.espAction(item.entity_id, "press", undefined, toastMsg);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<button
        type="button"
        ?disabled=${buttonUnavailable}
        @click=${onRun}
        class="btn btn-secondary btn-compact"
      >
        ${t("action.run", undefined, overlay)}
      </button>`,
    });
  }

  if (dom === "update") {
    const hasUpdate = st === "on";
    return renderSettingsRow({
      label,
      control: html`<span class="chip ${hasUpdate ? "chip-warning" : ""}">${hasUpdate ? t("status.update", undefined, overlay) : t("status.up_to_date", undefined, overlay)}</span>
        ${hasUpdate
          ? html`<button
              type="button"
              @click=${() => void store.entity.espAction(item.entity_id, "install")}
              class="btn btn-primary btn-compact"
            >
              ${t("action.install", undefined, overlay)}
            </button>`
          : nothing}`,
    });
  }

  const displayVal = unavailable
    ? "—"
    : item.unit && Number.isFinite(Number(st))
      ? `${fmtNumber(Number(st), store.hass)} ${item.unit}`
      : st || "—";

  return html`<div class="kv-row">
    <span>${label}</span>
    <strong>${displayVal}</strong>
  </div>`;
}

export function renderPrefControlRow(
  store: StudioStore,
  pref: DevicePrefItem,
  labelOverride?: string,
): TemplateResult | typeof nothing {
  const overlay = getLocaleOverlay(store);
  const label =
    labelOverride || tPrefLabel(pref.key, pref.label || entityLabel(pref.key), overlay);
  const dom = pref.domain;
  const val = pref.value;

  if (dom === "switch") {
    const isOn = Boolean(val);
    const onToggle = (ev: Event): void => {
      const checked = (ev.currentTarget as HTMLInputElement).checked;
      store.entity.stageDeviceSetting(pref.key, checked);
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        .checked=${live(isOn)}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }

  if (dom === "select") {
    const opts = pref.options || [];
    const st = String(val ?? "");
    const onChange = (ev: Event): void => {
      const nextVal = (ev.currentTarget as HTMLSelectElement).value;
      store.entity.stageDeviceSetting(pref.key, nextVal);
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} .value=${live(st)} @change=${onChange}>
        ${opts.map(
          (opt) =>
            html`<option value=${opt} .selected=${live(opt === st)}>
              ${tPrefOption(pref.key, opt, overlay)}
            </option>`,
        )}
      </select>`,
    });
  }

  if (dom === "number") {
    const min = pref.min ?? 0;
    const max = pref.max ?? 100;
    const step = pref.step ?? 1;
    const numVal = Number.isFinite(Number(val)) ? Number(val) : min;
    if (pref.unit === ":00") {
      return renderHourSelectRow({
        label,
        ariaLabel: label,
        value: numVal,
        is24h: isDeviceTime24h(store),
        hass: store.hass,
        onCommit: (raw) => store.entity.stageDeviceSetting(pref.key, raw),
      });
    }
    if (max - min <= 250) {
      return renderSettingsRow({
        label,
        control: renderRangeControl({
          ariaLabel: label,
          value: numVal,
          min,
          max,
          step,
          unit: pref.unit,
          is24h: isDeviceTime24h(store),
          hass: store.hass,
          onCommit: (raw) => store.entity.stageDeviceSetting(pref.key, raw),
        }),
      });
    }
    return renderSettingsRow({
      label,
      control: html`<input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          .value=${focusSafe(String(numVal))}
          @change=${(ev: Event) => {
            const raw = Number((ev.currentTarget as HTMLInputElement).value);
            if (Number.isFinite(raw)) {
              store.entity.stageDeviceSetting(pref.key, raw);
            }
          }}
        />
        ${pref.unit ? html`<span class="help-text">${pref.unit}</span>` : nothing}`,
    });
  }

  return nothing;
}

type QuickActionKind =
  | "find_my"
  | "voice"
  | "screensaver"
  | "hibernate"
  | "restart"
  | "other";

const QUICK_ACTION_RANK: Record<QuickActionKind, number> = {
  find_my: 0,
  voice: 1,
  screensaver: 2,
  hibernate: 3,
  restart: 4,
  other: 5,
};

function quickActionKind(item: EspHomeEntityItem): QuickActionKind {
  const nameLow = (item.name || "").toLowerCase();
  const idTail = item.entity_id.includes(".")
    ? (item.entity_id.split(".", 2)[1] ?? item.entity_id).toLowerCase()
    : item.entity_id.toLowerCase();

  if (
    item.device_class === "identify" ||
    nameLow.includes("find my") ||
    idTail.endsWith("find_my_device") ||
    idTail.includes("_find_my")
  ) {
    return "find_my";
  }
  if (
    item.device_class === "restart" ||
    nameLow.includes("restart") ||
    idTail.endsWith("_actions_restart_device")
  ) {
    return "restart";
  }
  if (nameLow.includes("screensaver") || idTail.includes("screensaver")) {
    return "screensaver";
  }
  if (nameLow.includes("hibernate") || idTail.includes("hibernate")) {
    return "hibernate";
  }
  if (
    nameLow.includes("voice") ||
    nameLow.includes("assist") ||
    idTail.includes("trigger_voice") ||
    idTail.includes("trigger_va")
  ) {
    return "voice";
  }
  return "other";
}

function renderQuickActionIcon(kind: QuickActionKind): TemplateResult {
  if (kind === "find_my") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8m0-14a6 6 0 1 0 6 6 6 6 0 0 0-6-6m0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4m0-6a2 2 0 1 0 2 2 2 2 0 0 0-2-2Z"
      />
    </svg>`;
  }
  if (kind === "voice") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3m7 9c0 3.53-2.61 6.44-6 6.93V21h-2v-3.07c-3.39-.49-6-3.4-6-6.93h2a5 5 0 0 0 10 0h2Z"
      />
    </svg>`;
  }
  if (kind === "screensaver") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20 3H4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h6v2H7v2h10v-2h-3v-2h6a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2m0 13H4V5h16v11M11.2 6.8a3.8 3.8 0 1 0 2.4 6 3.5 3.5 0 0 1-2.4-6m5.3-.6.65 1.65 1.65.65-1.65.65-.65 1.65-.65-1.65-1.65-.65 1.65-.65.65-1.65Z"
      />
    </svg>`;
  }
  if (kind === "hibernate") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12a6 6 0 0 1-6 6 6 6 0 0 1-6-6c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.961 7.961 0 0 0 4 12a8 8 0 0 0 8 8 8 8 0 0 0 8-8c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2V3Z"
      />
    </svg>`;
  }
  if (kind === "restart") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h10l-3.5 7H17l-7 13v-8H6l1-12Z" />
  </svg>`;
}

export function sortQuickActionButtons(
  items: readonly EspHomeEntityItem[],
): EspHomeEntityItem[] {
  return items.toSorted((a, b) => {
    const ra = QUICK_ACTION_RANK[quickActionKind(a)];
    const rb = QUICK_ACTION_RANK[quickActionKind(b)];
    if (ra !== rb) return ra - rb;
    return compareLocaleText(
      `${a.name || ""} ${a.entity_id}`,
      `${b.name || ""} ${b.entity_id}`,
    );
  });
}

export function renderQuickActionGrid(
  store: StudioStore,
  buttons: readonly EspHomeEntityItem[],
  forceDisabled = false,
): TemplateResult | typeof nothing {
  if (!buttons.length) return nothing;
  const overlay = getLocaleOverlay(store);
  const ordered = sortQuickActionButtons(buttons);
  return html`<div
    class="quick-action-grid"
    role="group"
    aria-label=${t("card.quick_actions", undefined, overlay)}
  >
    ${ordered.map((item) => {
      const kind = quickActionKind(item);
      const label = entityLabel(item.name || item.entity_id);
      const buttonUnavailable = forceDisabled || String(item.state ?? "") === "unavailable";
      const toastMsg =
        kind === "restart"
          ? t("sync.restarting_device", undefined, overlay)
          : kind === "hibernate"
            ? t("sync.hibernating_device", undefined, overlay)
            : t("sync.triggered_action", { label }, overlay);
      const onTrigger = (): void => {
        if (item.device_command) {
          void store.entity.runDeviceAction(item.device_command, toastMsg);
        } else {
          void store.entity.espAction(item.entity_id, "press", undefined, toastMsg);
        }
      };
      return html`<button
        type="button"
        data-entity-id=${item.entity_id}
        ?disabled=${buttonUnavailable}
        @click=${onTrigger}
        class="btn btn-secondary quick-action-btn"
      >
        ${renderQuickActionIcon(kind)}
        <span>${label}</span>
      </button>`;
    })}
  </div>`;
}
