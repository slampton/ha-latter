/**
 * Cards & Auto-Described Settings / Select / Switch / Range / Hour-Select Rows
 * (`components/controls/rows.ts`, `D-014`, `D-015`, `D-062`, `D-070`).
 */

import { t } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { CatalogChoice, HomeAssistant } from "../../types.js";
import {
  defaultLocaleTimeFormat,
  fmtNumber,
  formatHourSlot,
} from "../../utils/format.js";
import {
  autoWireDescribedBy,
  renderSelectOptions,
  resolveDescriptionId,
} from "./aria-helpers.js";

export interface CardRenderOptions {
  id?: string;
  title?: string;
  heading?: TemplateResult;
  subtitle?: string;
  headerActions?: TemplateResult | typeof nothing;
  footerActions?: TemplateResult | typeof nothing;
  contentClass?: string;
  danger?: boolean;
  handoffActive?: boolean;
  body: unknown;
}

export function renderCard(opts: CardRenderOptions): TemplateResult {
  const headingEl = opts.heading ?? html`<h3 class="card-title">${opts.title || ""}</h3>`;
  const headerInner =
    opts.subtitle || (opts.headerActions && opts.headerActions !== nothing)
      ? html`<div class="card-heading">
            ${headingEl}
            ${opts.subtitle ? html`<p class="card-subtitle">${opts.subtitle}</p>` : nothing}
          </div>
          ${opts.headerActions && opts.headerActions !== nothing
            ? html`<div class="card-header-actions">${opts.headerActions}</div>`
            : nothing}`
      : headingEl;
  const contentCls = opts.contentClass ? `card-content ${opts.contentClass}` : "card-content";
  return html`<div id=${opts.id || nothing} class="card${opts.danger ? " danger" : ""}${opts.handoffActive ? " handoff-active" : ""}">
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
  description?: string | TemplateResult | typeof nothing;
  descId?: string;
  stacked?: boolean;
  control: unknown;
}

export function renderSettingsRow(opts: SettingsRowOptions): TemplateResult {
  const hasDescription = Boolean(opts.description && opts.description !== nothing);
  const resolvedDescId = resolveDescriptionId({
    descId: opts.descId,
    forId: opts.forId,
    id: opts.id,
    label: opts.label,
    hasDescription,
  });
  const labelEl =
    opts.labelHtml ??
    (opts.forId
      ? html`<label for=${opts.forId} class="row-label">${opts.label || ""}</label>`
      : html`<span class="row-label">${opts.label || ""}</span>`);
  return html`<div id=${opts.id || nothing} class="settings-row${opts.stacked ? " stacked" : ""}">
    <div class="settings-row-text">
      ${labelEl}
      ${hasDescription
        ? html`<p id=${resolvedDescId} class="row-description">${opts.description}</p>`
        : nothing}
    </div>
    <div class="settings-row-control" ${resolvedDescId ? autoWireDescribedBy(resolvedDescId) : nothing}>
      ${opts.control}
    </div>
  </div>`;
}

export interface SelectRowOptions {
  rowId?: string;
  id?: string;
  label: string;
  ariaLabel?: string;
  description?: string | TemplateResult | typeof nothing;
  descId?: string;
  disabled?: boolean;
  value: string | null | undefined;
  choices?: readonly CatalogChoice[];
  emptyOptionLabel?: string;
  rawOptions?: ReadonlyArray<{ value: string; label: string }>;
  onChange: (value: string) => void;
}

export function renderSelectRow(opts: SelectRowOptions): TemplateResult {
  const cur = String(opts.value ?? "");
  const resolvedDescId = resolveDescriptionId({
    descId: opts.descId,
    forId: opts.id,
    id: opts.rowId,
    label: opts.label,
    hasDescription: Boolean(opts.description && opts.description !== nothing),
  });
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: resolvedDescId || undefined,
    control: html`<select
      id=${opts.id || nothing}
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      aria-describedby=${resolvedDescId || nothing}
      ?disabled=${Boolean(opts.disabled)}
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
  description?: string | TemplateResult | typeof nothing;
  descId?: string;
  disabled?: boolean;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function renderSwitchRow(opts: SwitchRowOptions): TemplateResult {
  const resolvedDescId = resolveDescriptionId({
    descId: opts.descId,
    forId: opts.id,
    id: opts.rowId,
    label: opts.label,
    hasDescription: Boolean(opts.description && opts.description !== nothing),
  });
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: resolvedDescId || undefined,
    control: html`<input
      type="checkbox"
      id=${opts.id || nothing}
      role="switch"
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      aria-describedby=${resolvedDescId || nothing}
      ?disabled=${Boolean(opts.disabled)}
      .checked=${opts.checked}
      @change=${(ev: Event) => opts.onChange((ev.currentTarget as HTMLInputElement).checked)}
      class="switch"
    />`,
  });
}

export interface RangeControlOptions {
  id?: string;
  ariaLabel: string;
  ariaDescribedBy?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  is24h?: boolean;
  maximumFractionDigits?: number;
  disabled?: boolean;
  hass?: HomeAssistant | null;
  onCommit: (value: number) => void;
  onInput?: (value: number) => void;
}

export function renderRangeControl(opts: RangeControlOptions): TemplateResult {
  const step = opts.step ?? 1;
  const maxFrac = opts.maximumFractionDigits ?? (Number.isInteger(step) ? 0 : 1);
  const isHourSlot = opts.unit === ":00";
  const resolvedIs24h = opts.is24h ?? defaultLocaleTimeFormat(opts.hass).startsWith("24");
  const unitSuffix =
    !isHourSlot && opts.unit ? (opts.unit === "%" ? "%" : ` ${opts.unit}`) : "";
  const formatVal = (v: number): string =>
    isHourSlot
      ? formatHourSlot(v, resolvedIs24h)
      : `${fmtNumber(v, opts.hass, maxFrac)}${unitSuffix}`;
  const initialText = formatVal(opts.value);

  const handleLiveInput = (ev: Event): void => {
    const inp = ev.currentTarget as HTMLInputElement;
    const raw = Number(inp.value);
    if (!Number.isFinite(raw)) return;
    const nextText = formatVal(raw);
    inp.setAttribute("aria-valuetext", nextText);
    const prev = inp.previousElementSibling;
    if (prev && prev.classList.contains("kv-value")) {
      prev.textContent = nextText;
    }
    opts.onInput?.(raw);
  };

  const handleCommit = (ev: Event): void => {
    const raw = Number((ev.currentTarget as HTMLInputElement).value);
    if (Number.isFinite(raw)) {
      opts.onCommit(raw);
    }
  };

  return html`<span class="kv-value">${initialText}</span>
    <input
      type="range"
      id=${opts.id || nothing}
      aria-label=${opts.ariaLabel}
      aria-describedby=${opts.ariaDescribedBy || nothing}
      aria-valuetext=${initialText}
      min=${String(opts.min)}
      max=${String(opts.max)}
      step=${String(step)}
      ?disabled=${Boolean(opts.disabled)}
      .value=${String(opts.value)}
      @input=${handleLiveInput}
      @change=${handleCommit}
    />`;
}

export interface RangeRowOptions extends Omit<RangeControlOptions, "ariaLabel"> {
  rowId?: string;
  label: string;
  ariaLabel?: string;
  description?: string | TemplateResult | typeof nothing;
  descId?: string;
}

export function renderRangeRow(opts: RangeRowOptions): TemplateResult {
  const resolvedDescId = resolveDescriptionId({
    descId: opts.descId,
    forId: opts.id,
    id: opts.rowId,
    label: opts.label,
    hasDescription: Boolean(opts.description && opts.description !== nothing),
  });
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: resolvedDescId || undefined,
    control: renderRangeControl({
      ...opts,
      ariaLabel: opts.ariaLabel || opts.label,
      ariaDescribedBy: resolvedDescId || opts.ariaDescribedBy,
    }),
  });
}

export interface HourSelectControlOptions {
  id?: string;
  ariaLabel: string;
  ariaDescribedBy?: string;
  value: number;
  is24h?: boolean;
  disabled?: boolean;
  hass?: HomeAssistant | null;
  mixed?: boolean;
  mixedLabel?: string;
  onCommit: (hour: number) => void;
}

export function renderHourSelectControl(opts: HourSelectControlOptions): TemplateResult {
  const resolvedIs24h = opts.is24h ?? defaultLocaleTimeFormat(opts.hass).startsWith("24");
  const normalizedHour = ((Math.round(opts.value) % 24) + 24) % 24;
  const selectValue = opts.mixed ? "__mixed__" : String(normalizedHour);
  return html`<select
    id=${opts.id || nothing}
    aria-label=${opts.ariaLabel}
    aria-describedby=${opts.ariaDescribedBy || nothing}
    ?disabled=${Boolean(opts.disabled)}
    .value=${selectValue}
    @change=${(ev: Event) => {
      const raw = (ev.currentTarget as HTMLSelectElement).value;
      if (raw === "__mixed__") return;
      const nextHour = Number(raw);
      if (Number.isFinite(nextHour)) {
        opts.onCommit(((Math.round(nextHour) % 24) + 24) % 24);
      }
    }}
  >
    ${opts.mixed
      ? html`<option value="__mixed__" selected disabled>
          ${opts.mixedLabel || t("batch.mixed_badge")}
        </option>`
      : nothing}
    ${Array.from({ length: 24 }, (_, h) => {
      const valStr = String(h);
      return html`<option value=${valStr} ?selected=${!opts.mixed && h === normalizedHour}>
        ${formatHourSlot(h, resolvedIs24h)}
      </option>`;
    })}
  </select>`;
}

export interface HourSelectRowOptions extends Omit<HourSelectControlOptions, "ariaLabel"> {
  rowId?: string;
  label: string;
  ariaLabel?: string;
  description?: string | TemplateResult | typeof nothing;
  descId?: string;
}

export function renderHourSelectRow(opts: HourSelectRowOptions): TemplateResult {
  const resolvedDescId = resolveDescriptionId({
    descId: opts.descId,
    forId: opts.id,
    id: opts.rowId,
    label: opts.label,
    hasDescription: Boolean(opts.description && opts.description !== nothing),
  });
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: resolvedDescId || undefined,
    control: renderHourSelectControl({
      ...opts,
      ariaLabel: opts.ariaLabel || opts.label,
      ariaDescribedBy: resolvedDescId || opts.ariaDescribedBy,
    }),
  });
}
