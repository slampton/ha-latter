/**
 * Shared Lit UI controls, declarative card/row/slot helpers, native ESPHome entity rows, and table headers.
 * Note: Event bindings (`@click`, `@change`) always precede `class="..."` / `role="radio"` attributes.
 */

import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { CatalogChoice, EspHomeEntityItem } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

export interface CardRenderOptions {
  id?: string;
  title?: string;
  heading?: TemplateResult;
  subtitle?: string;
  headerActions?: TemplateResult | typeof nothing;
  footerActions?: TemplateResult | typeof nothing;
  contentClass?: string;
  danger?: boolean;
  body: unknown;
}

export function renderCard(opts: CardRenderOptions): TemplateResult {
  const headingEl = opts.heading ?? html`<h3 class="card-title">${opts.title || ""}</h3>`;
  const headerInner =
    opts.subtitle || opts.headerActions
      ? html`<div class="card-heading">
            ${headingEl}
            ${opts.subtitle ? html`<p class="card-subtitle">${opts.subtitle}</p>` : nothing}
          </div>
          ${opts.headerActions && opts.headerActions !== nothing
            ? html`<div class="card-header-actions">${opts.headerActions}</div>`
            : nothing}`
      : headingEl;
  const contentCls = opts.contentClass ? `card-content ${opts.contentClass}` : "card-content";
  return html`<div id=${opts.id || nothing} class="card${opts.danger ? " danger" : ""}">
    <div class="card-header">${headerInner}</div>
    <div class=${contentCls}>${opts.body}</div>
    ${opts.footerActions && opts.footerActions !== nothing
      ? html`<div class="card-actions">${opts.footerActions}</div>`
      : nothing}
  </div>`;
}

export interface SettingsRowOptions {
  id?: string;
  label?: string;
  labelHtml?: TemplateResult;
  forId?: string;
  description?: string | TemplateResult;
  descId?: string;
  stacked?: boolean;
  control: unknown;
}

export function renderSettingsRow(opts: SettingsRowOptions): TemplateResult {
  const labelEl =
    opts.labelHtml ??
    (opts.forId
      ? html`<label for=${opts.forId} class="row-label">${opts.label || ""}</label>`
      : html`<span class="row-label">${opts.label || ""}</span>`);
  return html`<div id=${opts.id || nothing} class="settings-row${opts.stacked ? " stacked" : ""}">
    <div class="settings-row-text">
      ${labelEl}
      ${opts.description
        ? html`<p id=${opts.descId || nothing} class="row-description">${opts.description}</p>`
        : nothing}
    </div>
    <div class="settings-row-control">${opts.control}</div>
  </div>`;
}

export interface SelectRowOptions {
  rowId?: string;
  id?: string;
  label: string;
  ariaLabel?: string;
  description?: string | TemplateResult;
  descId?: string;
  value: string | null | undefined;
  choices?: readonly CatalogChoice[];
  emptyOptionLabel?: string;
  rawOptions?: ReadonlyArray<{ value: string; label: string }>;
  onChange: (value: string) => void;
}

export function renderSelectRow(opts: SelectRowOptions): TemplateResult {
  const cur = String(opts.value ?? "");
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: opts.descId,
    control: html`<select
      id=${opts.id || nothing}
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .value=${cur}
      @change=${(ev: Event) => opts.onChange((ev.currentTarget as HTMLSelectElement).value)}
    >
      ${opts.rawOptions
        ? opts.rawOptions.map(
            (o) => html`<option value=${o.value} ?selected=${o.value === cur}>${o.label}</option>`,
          )
        : renderSelectOptions(opts.choices, cur, opts.emptyOptionLabel)}
    </select>`,
  });
}

export interface SwitchRowOptions {
  rowId?: string;
  id?: string;
  label: string;
  ariaLabel?: string;
  description?: string | TemplateResult;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function renderSwitchRow(opts: SwitchRowOptions): TemplateResult {
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    control: html`<input
      type="checkbox"
      id=${opts.id || nothing}
      role="switch"
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .checked=${opts.checked}
      @change=${(ev: Event) => opts.onChange((ev.currentTarget as HTMLInputElement).checked)}
      class="switch"
    />`,
  });
}

export interface EntitySlotListOptions {
  id: string;
  items: readonly string[];
  choices: readonly CatalogChoice[] | undefined;
  emptyOptionLabel: string;
  emptyStateText: string;
  selectAriaLabel: string;
  removeAriaLabel: string;
  slotLabel?: (idx: number) => string;
  extraActions?: (item: string, idx: number) => TemplateResult | typeof nothing;
  onChange: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

export function renderEntitySlotList(opts: EntitySlotListOptions): TemplateResult {
  return html`<div id=${opts.id} class="stack">
    ${opts.items.length
      ? opts.items.map(
          (val, idx) => html`<div class="list-row">
            <div class="stacked-field list-row-grow">
              ${opts.slotLabel
                ? html`<span class="field-label">${opts.slotLabel(idx)}</span>`
                : nothing}
              <select
                aria-label=${opts.selectAriaLabel}
                .value=${val}
                @change=${(ev: Event) =>
                  opts.onChange(idx, (ev.currentTarget as HTMLSelectElement).value)}
              >
                ${renderSelectOptions(opts.choices, val, opts.emptyOptionLabel)}
              </select>
            </div>
            ${opts.extraActions ? opts.extraActions(val, idx) : nothing}
            ${renderTrashIconButton(opts.removeAriaLabel, () => opts.onRemove(idx))}
          </div>`,
        )
      : html`<p class="empty-state">${opts.emptyStateText}</p>`}
  </div>`;
}

export function renderSelectOptions(
  choices: readonly CatalogChoice[] | undefined,
  selectedId: string | null | undefined,
  emptyOptionLabel = "None",
): TemplateResult[] {
  const cur = String(selectedId || "");
  const list = choices || [];
  const hasSelected = !cur || list.some((c) => c.id === cur);
  const out: TemplateResult[] = [
    html`<option value="" ?selected=${cur === ""}>${emptyOptionLabel}</option>`,
  ];
  if (cur && !hasSelected) {
    out.push(html`<option value=${cur} selected>${cur} (missing)</option>`);
  }
  for (const item of list) {
    out.push(
      html`<option value=${item.id} ?selected=${item.id === cur}>${item.name || item.id}</option>`,
    );
  }
  return out;
}

export function renderTrashIconButton(ariaLabel: string, onRemove: () => void): TemplateResult {
  return html`<button
    type="button"
    aria-label=${ariaLabel}
    @click=${onRemove}
    class="btn-icon danger"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9m0 5h2v9H9V8m4 0h2v9h-2V8Z" />
    </svg>
  </button>`;
}

export function renderSortHeader(
  store: StudioStore,
  field: "title" | "model" | "area" | "group" | "status",
  label: string,
): TemplateResult {
  const isActive = store.deviceSortField === field;
  const ariaSort = isActive ? (store.deviceSortAsc ? "ascending" : "descending") : "none";
  const onSort = (): void => {
    if (store.deviceSortField === field) {
      store.deviceSortAsc = !store.deviceSortAsc;
    } else {
      store.deviceSortField = field;
      store.deviceSortAsc = true;
    }
    store.host.requestUpdate();
  };
  return html`<th aria-sort=${ariaSort}>
    <button type="button" @click=${onSort} class="sort-btn">${label}</button>
  </th>`;
}

export function renderNativeControlRow(store: StudioStore, item: EspHomeEntityItem): TemplateResult {
  const label = entityLabel(item.name || item.entity_id);
  const dom = item.domain;
  const st = String(item.state ?? "");
  const unavailable = st === "unavailable" || st === "unknown";

  if (dom === "switch") {
    const isOn = st === "on";
    const onToggle = (ev: Event): void => {
      const checked = (ev.currentTarget as HTMLInputElement).checked;
      void store.espAction(item.entity_id, checked ? "turn_on" : "turn_off", checked ? "on" : "off");
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        ?disabled=${unavailable}
        .checked=${isOn}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }

  if (dom === "select") {
    const opts = item.options || [];
    const onChange = (ev: Event): void => {
      void store.espSelect(item.entity_id, (ev.currentTarget as HTMLSelectElement).value);
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${st} @change=${onChange}>
        ${opts.map((opt) => html`<option value=${opt} ?selected=${opt === st}>${opt}</option>`)}
      </select>`,
    });
  }

  if (dom === "number") {
    const min = item.min ?? 0;
    const max = item.max ?? 100;
    const step = item.step ?? 1;
    const numVal = Number.isFinite(Number(st)) ? Number(st) : min;
    const unitSuffix = item.unit ? ` ${item.unit}` : "";
    const onCommit = (ev: Event): void => {
      const raw = Number((ev.currentTarget as HTMLInputElement).value);
      if (Number.isFinite(raw)) {
        void store.espNumber(item.entity_id, raw);
      }
    };
    if (max - min <= 250 && item.mode !== "box") {
      return renderSettingsRow({
        label,
        control: html`<span class="kv-value">${fmtNumber(numVal, store.hass)}${unitSuffix}</span>
          <input
            type="range"
            aria-label=${label}
            min=${String(min)}
            max=${String(max)}
            step=${String(step)}
            ?disabled=${unavailable}
            .value=${String(numVal)}
            @change=${onCommit}
          />`,
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
          .value=${String(numVal)}
          @change=${onCommit}
        />
        ${item.unit ? html`<span class="help-text">${item.unit}</span>` : nothing}`,
    });
  }

  if (dom === "button") {
    const buttonUnavailable = st === "unavailable";
    const toastMsg = label.toLowerCase().includes("restart")
      ? "Restarting Device…"
      : `Triggered "${label}"`;
    return renderSettingsRow({
      label,
      control: html`<button
        type="button"
        ?disabled=${buttonUnavailable}
        @click=${() => void store.espAction(item.entity_id, "press", undefined, toastMsg)}
        class="btn btn-secondary btn-compact"
      >
        Run
      </button>`,
    });
  }

  if (dom === "update") {
    const hasUpdate = st === "on";
    return renderSettingsRow({
      label,
      control: html`<span class="chip ${hasUpdate ? "chip-warning" : ""}">${hasUpdate ? "Update available" : "Up to date"}</span>
        ${hasUpdate
          ? html`<button
              type="button"
              @click=${() => void store.espAction(item.entity_id, "install")}
              class="btn btn-primary btn-compact"
            >
              Install
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

const QUICK_ACTION_ORDER: readonly string[] = [
  "find my",
  "trigger voice",
  "screensaver",
  "restart",
];

function renderQuickActionIcon(item: EspHomeEntityItem): TemplateResult {
  const hay = `${item.name || ""} ${item.entity_id}`.toLowerCase();
  if (hay.includes("find my") || hay.includes("find_my") || item.device_class === "identify") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8m0-14a6 6 0 1 0 6 6 6 6 0 0 0-6-6m0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4m0-6a2 2 0 1 0 2 2 2 2 0 0 0-2-2Z"
      />
    </svg>`;
  }
  if (hay.includes("voice") || hay.includes("trigger_va") || hay.includes("assist")) {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3m7 9c0 3.53-2.61 6.44-6 6.93V21h-2v-3.07c-3.39-.49-6-3.4-6-6.93h2a5 5 0 0 0 10 0h2Z"
      />
    </svg>`;
  }
  if (hay.includes("screensaver") || hay.includes("sleep")) {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M17.75 4.09L15.22 6.03l.91 3.06-2.63-1.81-2.63 1.81.91-3.06-2.53-1.94L12.44 4l1.06-3 1.06 3 3.19.09m3.5 6.91-1.64 1.25.59 1.98-1.7-1.17-1.7 1.17.59-1.98L15.75 11l2.06-.05L18.5 9l.69 1.95 2.06.05m-2.28 4.95c.83-.08 1.72 1.1 1.19 1.85-.32.45-.66.87-1.08 1.27C15.17 23 8.84 23 4.94 19.07c-3.91-3.9-3.91-10.24 0-14.14.4-.4.82-.76 1.27-1.08.75-.53 1.93.36 1.85 1.19-.27 2.86.69 5.83 2.89 8.02a9.96 9.96 0 0 0 8.02 2.89m-1.64 2.02a12.08 12.08 0 0 1-7.8-3.47c-2.17-2.19-3.33-5-3.49-7.82-2.81 3.14-2.7 7.96.31 10.98 3.02 3.01 7.84 3.12 10.98.31Z"
      />
    </svg>`;
  }
  if (hay.includes("restart") || item.device_class === "restart") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 4c2.1 0 4.1.8 5.6 2.3 3.1 3.1 3.1 8.2 0 11.3-1.8 1.9-4.3 2.6-6.7 2.3l.5-2c1.7.2 3.5-.4 4.8-1.7 2.3-2.3 2.3-6.1 0-8.5C15.1 6.6 13.5 6 12 6v4.6l-5-5 5-5V4M6.3 17.6C3.7 15 3.3 11 5.1 7.9l1.5 1.5c-1.1 2.2-.7 5 1.2 6.8.5.5 1.1.9 1.8 1.2l-.6 2c-1-.4-1.9-1-2.7-1.8Z"
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
  return [...items].sort((a, b) => {
    const ha = `${a.name || ""} ${a.entity_id}`.toLowerCase();
    const hb = `${b.name || ""} ${b.entity_id}`.toLowerCase();
    const ia = QUICK_ACTION_ORDER.findIndex((k) => ha.includes(k));
    const ib = QUICK_ACTION_ORDER.findIndex((k) => hb.includes(k));
    const ra = ia >= 0 ? ia : QUICK_ACTION_ORDER.length;
    const rb = ib >= 0 ? ib : QUICK_ACTION_ORDER.length;
    if (ra !== rb) return ra - rb;
    return ha.localeCompare(hb);
  });
}

export function renderQuickActionGrid(
  store: StudioStore,
  buttons: readonly EspHomeEntityItem[],
): TemplateResult | typeof nothing {
  if (!buttons.length) return nothing;
  const ordered = sortQuickActionButtons(buttons);
  return html`<div class="quick-action-grid" role="group" aria-label="Device Quick Actions">
    ${ordered.map((item) => {
      const label = entityLabel(item.name || item.entity_id);
      const buttonUnavailable = String(item.state ?? "") === "unavailable";
      const toastMsg = label.toLowerCase().includes("restart")
        ? "Restarting Device…"
        : `Triggered "${label}"`;
      return html`<button
        type="button"
        data-entity-id=${item.entity_id}
        ?disabled=${buttonUnavailable}
        @click=${() => void store.espAction(item.entity_id, "press", undefined, toastMsg)}
        class="btn btn-secondary quick-action-btn"
      >
        ${renderQuickActionIcon(item)}
        <span>${label}</span>
      </button>`;
    })}
  </div>`;
}
