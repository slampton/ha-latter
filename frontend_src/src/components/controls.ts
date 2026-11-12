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
    return renderSettingsRow({
      label,
      control: html`<button
        type="button"
        ?disabled=${unavailable}
        @click=${() => void store.espAction(item.entity_id, "press")}
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
