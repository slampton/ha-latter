/**
 * Shared Lit UI controls for Latter Studio (`D-014`, `D-015`, `D-024`, `D-062`, `D-064`):
 * - Cards & auto-described settings/select/switch/range rows (`aria-describedby` + live `aria-valuetext`)
 * - Shared confirmation `<dialog>` builder (`renderConfirmDialog`, `Q5`)
 * - Reusable WAI-ARIA 1.2 searchable entity combobox (`renderEntityCombobox`, `Q11`)
 * - Pointer drag-handle (`≡`) + keyboard focus-preserving `renderSortableList` & `renderPillList` (`U4`)
 * Note: Event bindings (`@click`, `@change`, `@input`) always precede `class="..."` / `role="radio"`.
 */

import { t, tPrefLabel, tPrefOption } from "../i18n/index.js";
import {
  Directive,
  directive,
  focusSafe,
  html,
  noChange,
  nothing,
  PartType,
  repeat,
  type ElementPart,
  type PartInfo,
  type TemplateResult,
} from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type {
  CatalogChoice,
  DevicePrefItem,
  EspHomeEntityItem,
  HomeAssistant,
} from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

function slugifyToken(raw: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < raw.length; i += 1) {
    hash ^= raw.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  const clean = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 28);
  // Prefix with non-hex ` row-desc-` / `z` so ID selectors never resemble hex literals.
  return clean ? `${clean}-${hash.toString(36)}` : `z${hash.toString(36)}`;
}

export function resolveDescriptionId(opts: {
  descId?: string;
  forId?: string;
  id?: string;
  label?: string;
  hasDescription: boolean;
}): string {
  if (!opts.hasDescription) return "";
  if (opts.descId) return opts.descId;
  if (opts.forId) return `${opts.forId}-desc`;
  if (opts.id) return `${opts.id}-desc`;
  return `row-desc-${slugifyToken(opts.label || "setting")}`;
}

class AutoDescribeDirective extends Directive {
  constructor(partInfo: PartInfo) {
    super(partInfo);
    if (partInfo.type !== PartType.ELEMENT) {
      throw new Error("autoWireDescribedBy() must be used as an element directive");
    }
  }

  render(_descId: string): typeof nothing {
    return nothing;
  }

  override update(part: ElementPart, [descId]: [string]): typeof noChange {
    if (descId && part.element) {
      const container = part.element;
      const apply = (): void => {
        const target = container.querySelector(
          "input:not([type='hidden']), select, textarea, [role='combobox']",
        );
        if (target && !target.hasAttribute("aria-describedby")) {
          target.setAttribute("aria-describedby", descId);
        }
      };
      apply();
      queueMicrotask(apply);
    }
    return noChange;
  }
}

const autoWireDescribedBy = directive(AutoDescribeDirective);

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
  maximumFractionDigits?: number;
  disabled?: boolean;
  hass?: HomeAssistant | null;
  onCommit: (value: number) => void;
  onInput?: (value: number) => void;
}

export function renderRangeControl(opts: RangeControlOptions): TemplateResult {
  const step = opts.step ?? 1;
  const maxFrac =
    opts.maximumFractionDigits ?? (Number.isInteger(step) ? 0 : 1);
  const unitSuffix = opts.unit ? ` ${opts.unit}` : "";
  const formatVal = (v: number): string => `${fmtNumber(v, opts.hass, maxFrac)}${unitSuffix}`;
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

export interface RangeRowOptions extends RangeControlOptions {
  rowId?: string;
  label: string;
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

// ---------------------------------------------------------------------------
// Shared Confirmation <dialog> Builder (Q5 / D-064)
// ---------------------------------------------------------------------------

export interface ConfirmDialogOptions {
  id: string;
  open?: boolean;
  title: string;
  consequence: string | TemplateResult;
  blastRadiusCount?: number | null;
  blastRadiusLabel?: string;
  extraBody?: TemplateResult | typeof nothing;
  confirmLabel: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  confirmDisabled?: boolean;
  confirmButtonId?: string;
  onConfirm: () => void;
  onCancel: () => void;
  onDownloadBackupFirst?: (() => void) | null;
  downloadBackupLabel?: string;
  overlay?: Readonly<Record<string, string>> | null;
}

export function syncDialogElement(
  dlg: HTMLDialogElement | null | undefined,
  wantOpen: boolean,
): void {
  if (!dlg) return;
  if (!wantOpen) {
    if (dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
    return;
  }
  if (!dlg.open) {
    try {
      dlg.showModal();
    } catch {
      dlg.setAttribute("open", "");
    }
  }
}

export function renderConfirmDialog(opts: ConfirmDialogOptions): TemplateResult {
  const titleId = `${opts.id}-title`;
  const descId = `${opts.id}-desc`;
  const isDanger = opts.danger !== false;
  const count = opts.blastRadiusCount;
  const blastText =
    opts.blastRadiusLabel ||
    (count !== undefined && count !== null && count > 0
      ? count === 1
        ? t("confirm.blast_radius_one", undefined, opts.overlay)
        : t("confirm.blast_radius_many", { count }, opts.overlay)
      : "");

  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget) {
      opts.onCancel();
    }
  };

  return html`<dialog
    id=${opts.id}
    aria-labelledby=${titleId}
    aria-describedby=${descId}
    @cancel=${(ev: Event) => {
      ev.preventDefault();
      opts.onCancel();
    }}
    @click=${onBackdropClick}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id=${titleId} class="dialog-title">${opts.title}</h3>
        ${blastText
          ? html`<span class="chip ${isDanger ? "chip-warning" : "chip-primary"} confirm-blast-badge">
              ${blastText}
            </span>`
          : nothing}
      </div>
      ${opts.extraBody && opts.extraBody !== nothing ? opts.extraBody : nothing}
      <p id=${descId} class="dialog-text">${opts.consequence}</p>
      <div class="dialog-actions${opts.onDownloadBackupFirst ? " with-secondary" : ""}">
        ${opts.onDownloadBackupFirst
          ? html`<button
              type="button"
              @click=${opts.onDownloadBackupFirst}
              class="btn btn-text btn-compact"
            >
              ${opts.downloadBackupLabel ||
              t("action.download_backup_first", undefined, opts.overlay)}
            </button>`
          : nothing}
        <div class="dialog-actions-end">
          <button
            type="button"
            @click=${opts.onCancel}
            class="btn btn-secondary"
          >
            ${opts.cancelLabel || t("action.cancel", undefined, opts.overlay)}
          </button>
          <button
            type="button"
            id=${opts.confirmButtonId || nothing}
            ?disabled=${Boolean(opts.busy || opts.confirmDisabled)}
            @click=${opts.onConfirm}
            class="btn ${isDanger ? "btn-danger-filled" : "btn-primary"}"
          >
            ${opts.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  </dialog>`;
}

// ---------------------------------------------------------------------------
// Reusable WAI-ARIA 1.2 Searchable Entity Combobox (Q11 / D-062)
// ---------------------------------------------------------------------------

export interface ComboboxOptionItem {
  id: string;
  name?: string;
  domain?: string;
  area_name?: string;
  state_label?: string;
  state_tone?: string;
  icon?: string;
}

export interface EntityComboboxOptions {
  id: string;
  value: string | null | undefined;
  options: ReadonlyArray<ComboboxOptionItem> | undefined;
  onChange: (entityId: string) => void;
  onUiChange?: () => void;
  host?: { requestUpdate(): void } | null;
  ariaLabel?: string;
  ariaDescribedBy?: string;
  placeholder?: string;
  emptyOptionLabel?: string;
  allowClear?: boolean;
  disabled?: boolean;
  maxResults?: number;
  overlay?: Readonly<Record<string, string>> | null;
}

interface ComboboxUiState {
  open: boolean;
  query: string;
  activeIndex: number;
}

const COMBOBOX_STATE = new Map<string, ComboboxUiState>();

function getComboboxState(id: string): ComboboxUiState {
  let st = COMBOBOX_STATE.get(id);
  if (!st) {
    st = { open: false, query: "", activeIndex: 0 };
    COMBOBOX_STATE.set(id, st);
  }
  return st;
}

export function resetComboboxState(id?: string): void {
  if (id) {
    COMBOBOX_STATE.delete(id);
  } else {
    COMBOBOX_STATE.clear();
  }
}

function isOrderedSubsequence(needle: string, haystack: string): boolean {
  if (!needle) return true;
  if (needle.length > haystack.length) return false;
  let ni = 0;
  for (let hi = 0; hi < haystack.length && ni < needle.length; hi += 1) {
    if (haystack.charCodeAt(hi) === needle.charCodeAt(ni)) {
      ni += 1;
    }
  }
  return ni === needle.length;
}

export function matchComboboxOptions(
  options: ReadonlyArray<ComboboxOptionItem> | undefined,
  rawQuery: string,
  maxResults = 80,
): { items: ComboboxOptionItem[]; totalMatches: number } {
  const list = options || [];
  const cap = Math.max(1, maxResults);
  const query = String(rawQuery || "").trim().toLowerCase();
  if (!query) {
    return {
      items: list.slice(0, cap),
      totalMatches: list.length,
    };
  }

  const tokens = query.split(/\s+/).filter(Boolean);
  const scored: Array<{ item: ComboboxOptionItem; rank: number; labelLow: string }> = [];

  for (const item of list) {
    const idLow = String(item.id || "").toLowerCase();
    const objIdLow = idLow.includes(".") ? idLow.split(".", 2)[1] : idLow;
    const nameLow = String(item.name || item.id || "").toLowerCase();
    const areaLow = String(item.area_name || "").toLowerCase();
    const domLow = String(item.domain || (idLow.includes(".") ? idLow.split(".", 1)[0] : "")).toLowerCase();
    const combined = `${nameLow} ${areaLow} ${idLow} ${domLow}`;

    let matchedAll = true;
    let usedFuzzy = false;
    for (const tok of tokens) {
      if (combined.includes(tok)) {
        continue;
      }
      if (isOrderedSubsequence(tok, `${nameLow} ${idLow}`)) {
        usedFuzzy = true;
        continue;
      }
      matchedAll = false;
      break;
    }
    if (!matchedAll) continue;

    let rank = 4;
    if (!usedFuzzy) {
      if (nameLow === query || idLow === query || objIdLow === query) {
        rank = 0;
      } else if (nameLow.startsWith(query) || objIdLow.startsWith(query) || idLow.startsWith(query)) {
        rank = 1;
      } else if (nameLow.includes(query) || areaLow.includes(query)) {
        rank = 2;
      } else {
        rank = 3;
      }
    }
    scored.push({ item, rank, labelLow: nameLow });
  }

  scored.sort(
    (a, b) =>
      a.rank - b.rank ||
      a.labelLow.localeCompare(b.labelLow) ||
      a.item.id.localeCompare(b.item.id),
  );

  return {
    items: scored.slice(0, cap).map((s) => s.item),
    totalMatches: scored.length,
  };
}

function toneToChipClass(tone: string | undefined): string {
  if (tone === "primary") return "chip chip-primary";
  if (tone === "success") return "chip chip-success";
  if (tone === "warning") return "chip chip-warning";
  if (tone === "error") return "chip chip-error";
  return "chip";
}

export function renderEntityCombobox(opts: EntityComboboxOptions): TemplateResult {
  const ui = getComboboxState(opts.id);
  const curVal = String(opts.value ?? "").trim();
  const allOptions = opts.options || [];
  const maxResults = opts.maxResults ?? 80;
  const selectedOpt = curVal ? allOptions.find((o) => o.id === curVal) : undefined;
  const closedDisplayValue = curVal
    ? selectedOpt
      ? selectedOpt.name || selectedOpt.id
      : t("common.missing_suffix", { id: curVal }, opts.overlay)
    : "";

  const { items: matchedItems, totalMatches } = matchComboboxOptions(
    allOptions,
    ui.open ? ui.query : "",
    maxResults,
  );
  const clampedActiveIdx =
    matchedItems.length > 0
      ? Math.max(0, Math.min(matchedItems.length - 1, ui.activeIndex))
      : -1;

  const listboxId = `${opts.id}-listbox`;
  const optionDomId = (idx: number): string => `${opts.id}-opt-${idx}`;
  const activeDescendantId =
    ui.open && clampedActiveIdx >= 0 ? optionDomId(clampedActiveIdx) : "";

  const notifyUi = (rootEl?: Element | null): void => {
    opts.onUiChange?.();
    opts.host?.requestUpdate();
    if (!opts.onUiChange && !opts.host && rootEl) {
      const rootNode = typeof rootEl.getRootNode === "function" ? rootEl.getRootNode() : null;
      const hostEl =
        rootNode && "host" in rootNode
          ? ((rootNode as ShadowRoot).host as unknown as { requestUpdate?: () => void })
          : null;
      hostEl?.requestUpdate?.();
    }
  };

  const scrollActiveIntoView = (inputEl: Element | null, nextIdx: number): void => {
    if (!inputEl || nextIdx < 0) return;
    requestAnimationFrame(() => {
      const wrap = inputEl.closest(".combobox");
      const li = wrap?.querySelector(`#${CSS.escape(optionDomId(nextIdx))}`) as HTMLElement | null;
      li?.scrollIntoView?.({ block: "nearest" });
    });
  };

  const commitSelection = (nextId: string, sourceEl?: Element | null): void => {
    ui.open = false;
    ui.query = "";
    ui.activeIndex = 0;
    if (nextId !== curVal) {
      opts.onChange(nextId);
    }
    notifyUi(sourceEl);
  };

  const openMenu = (sourceEl: Element | null): void => {
    if (opts.disabled || ui.open) return;
    ui.open = true;
    ui.query = "";
    const curIdx = curVal ? matchedItems.findIndex((o) => o.id === curVal) : -1;
    ui.activeIndex = curIdx >= 0 ? curIdx : 0;
    notifyUi(sourceEl);
  };

  const onInput = (ev: Event): void => {
    const inp = ev.currentTarget as HTMLInputElement;
    // Typing ONLY filters options; NEVER mutates the bound entity selection!
    ui.open = true;
    ui.query = inp.value;
    ui.activeIndex = 0;
    notifyUi(inp);
  };

  const onKeyDown = (ev: KeyboardEvent): void => {
    const inp = ev.currentTarget as HTMLInputElement;
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      if (!ui.open) {
        openMenu(inp);
        return;
      }
      if (matchedItems.length > 0) {
        const nextIdx = (clampedActiveIdx + 1) % matchedItems.length;
        ui.activeIndex = nextIdx;
        notifyUi(inp);
        scrollActiveIntoView(inp, nextIdx);
      }
      return;
    }
    if (ev.key === "ArrowUp") {
      ev.preventDefault();
      if (!ui.open) {
        ui.open = true;
        ui.query = "";
        ui.activeIndex = Math.max(0, matchedItems.length - 1);
        notifyUi(inp);
        return;
      }
      if (matchedItems.length > 0) {
        const nextIdx = (clampedActiveIdx - 1 + matchedItems.length) % matchedItems.length;
        ui.activeIndex = nextIdx;
        notifyUi(inp);
        scrollActiveIntoView(inp, nextIdx);
      }
      return;
    }
    if (ui.open && ev.key === "Home" && matchedItems.length > 0) {
      ev.preventDefault();
      ui.activeIndex = 0;
      notifyUi(inp);
      scrollActiveIntoView(inp, 0);
      return;
    }
    if (ui.open && ev.key === "End" && matchedItems.length > 0) {
      ev.preventDefault();
      const last = matchedItems.length - 1;
      ui.activeIndex = last;
      notifyUi(inp);
      scrollActiveIntoView(inp, last);
      return;
    }
    if (ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229) {
      if (ui.open) {
        ev.preventDefault();
        ev.stopPropagation();
        if (clampedActiveIdx >= 0 && matchedItems[clampedActiveIdx]) {
          commitSelection(matchedItems[clampedActiveIdx].id, inp);
        }
      }
      return;
    }
    if (ev.key === "Escape") {
      if (ui.open) {
        ev.preventDefault();
        ev.stopPropagation();
        ui.open = false;
        ui.query = "";
        inp.value = closedDisplayValue;
        notifyUi(inp);
      }
    }
  };

  const onFocusOut = (ev: FocusEvent): void => {
    const wrap = ev.currentTarget as HTMLElement;
    const rel = ev.relatedTarget as Node | null;
    if (rel && wrap.contains(rel)) {
      return;
    }
    if (ui.open) {
      ui.open = false;
      ui.query = "";
      const inp = wrap.querySelector("input[role='combobox']") as HTMLInputElement | null;
      if (inp) {
        inp.value = closedDisplayValue;
      }
      notifyUi(wrap);
    }
  };

  const showClear = opts.allowClear !== false && Boolean(curVal) && !opts.disabled;
  const placeholderText =
    opts.placeholder ||
    (curVal
      ? closedDisplayValue
      : opts.emptyOptionLabel || t("combobox.placeholder", undefined, opts.overlay));

  return html`<div @focusout=${onFocusOut} class="combobox">
    <div class="combobox-input-wrap">
      <input
        type="text"
        id=${opts.id}
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        aria-autocomplete="list"
        aria-expanded=${ui.open ? "true" : "false"}
        aria-controls=${listboxId}
        aria-activedescendant=${activeDescendantId || nothing}
        aria-label=${opts.ariaLabel || nothing}
        aria-describedby=${opts.ariaDescribedBy || nothing}
        placeholder=${placeholderText}
        ?disabled=${Boolean(opts.disabled)}
        .value=${ui.open ? focusSafe(ui.query) : closedDisplayValue}
        @focus=${(ev: Event) => openMenu(ev.currentTarget as Element)}
        @click=${(ev: Event) => openMenu(ev.currentTarget as Element)}
        @input=${onInput}
        @keydown=${onKeyDown}
      />
      ${showClear
        ? html`<button
            type="button"
            aria-label=${t("combobox.clear", undefined, opts.overlay)}
            @pointerdown=${(ev: PointerEvent) => {
              ev.preventDefault();
              commitSelection("", ev.currentTarget as Element);
            }}
            @click=${(ev: Event) => commitSelection("", ev.currentTarget as Element)}
            class="combobox-clear"
          >
            ×
          </button>`
        : nothing}
    </div>
    <ul
      id=${listboxId}
      role="listbox"
      aria-label=${opts.ariaLabel || t("combobox.placeholder", undefined, opts.overlay)}
      class="combobox-listbox${ui.open ? "" : " hidden"}"
    >
      ${matchedItems.length === 0
        ? html`<li role="presentation" class="combobox-empty">
            ${t("combobox.no_matches", undefined, opts.overlay)}
          </li>`
        : repeat(
            matchedItems,
            (item) => item.id,
            (item, idx) => {
              const dom = item.domain || (item.id.includes(".") ? item.id.split(".", 1)[0] : "");
              const isSel = item.id === curVal;
              const isAct = idx === clampedActiveIdx;
              return html`<li
                id=${optionDomId(idx)}
                role="option"
                aria-selected=${isSel ? "true" : "false"}
                @pointerenter=${(ev: PointerEvent) => {
                  if (ui.activeIndex !== idx) {
                    ui.activeIndex = idx;
                    notifyUi(ev.currentTarget as Element);
                  }
                }}
                @pointerdown=${(ev: PointerEvent) => {
                  ev.preventDefault();
                  commitSelection(item.id, ev.currentTarget as Element);
                }}
                @click=${(ev: Event) => commitSelection(item.id, ev.currentTarget as Element)}
                class="combobox-option${isAct ? " active" : ""}"
              >
                <div class="combobox-option-main">
                  <span class="combobox-option-title">${item.name || item.id}</span>
                  <span class="combobox-option-id">${item.id}</span>
                </div>
                <span class="combobox-option-chips">
                  ${item.area_name ? html`<span class="chip">${item.area_name}</span>` : nothing}
                  ${dom ? html`<span class="chip">${dom}</span>` : nothing}
                  ${item.state_label
                    ? html`<span class=${toneToChipClass(item.state_tone)}>${item.state_label}</span>`
                    : nothing}
                </span>
              </li>`;
            },
          )}
      ${totalMatches > matchedItems.length
        ? html`<li role="presentation" class="combobox-footer">
            ${t(
              "combobox.showing_top",
              { shown: matchedItems.length, total: totalMatches },
              opts.overlay,
            )}
          </li>`
        : nothing}
    </ul>
  </div>`;
}

// ---------------------------------------------------------------------------
// Pointer Drag-and-Drop (`≡`) + Focus-Preserving Keyboard Sortable Lists & Pills (U4 / D-064)
// ---------------------------------------------------------------------------

interface ActiveDragSession {
  listId: string;
  pointerId: number;
  orientation: "vertical" | "horizontal";
  fromIndex: number;
  overIndex: number;
  insertAfter: boolean;
}

let activeDrag: ActiveDragSession | null = null;
const SORTABLE_LIVE_STATUS = new Map<string, string>();

function announceReorder(
  listId: string,
  itemLabel: string,
  toIndex: number,
  total: number,
  overlay: Readonly<Record<string, string>> | null | undefined,
  rootEl: Element | null,
): void {
  const msg = t(
    "common.reordered_status",
    { item: itemLabel, position: toIndex + 1, total },
    overlay,
  );
  SORTABLE_LIVE_STATUS.set(listId, msg);
  const liveEl = rootEl
    ?.closest("[data-sortable-list]")
    ?.querySelector("[data-sortable-live]") as HTMLElement | null;
  if (liveEl) {
    liveEl.textContent = msg;
  }
}

function clearDragDomClasses(listEl: Element | null): void {
  if (!listEl) return;
  for (const el of listEl.querySelectorAll(".dragging, .drag-over-before, .drag-over-after")) {
    el.classList.remove("dragging", "drag-over-before", "drag-over-after");
  }
}

function computeDropTargetIndex(
  fromIndex: number,
  overIndex: number,
  insertAfter: boolean,
  total: number,
): number {
  let target = insertAfter ? overIndex + 1 : overIndex;
  if (target > fromIndex) {
    target -= 1;
  }
  return Math.max(0, Math.min(total - 1, target));
}

function attachDragHandleHandlers(opts: {
  listId: string;
  orientation: "vertical" | "horizontal";
  idx: number;
  total: number;
  itemLabel: string;
  overlay?: Readonly<Record<string, string>> | null;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const onPointerDown = (ev: PointerEvent): void => {
    if (ev.button !== 0 || opts.total <= 1) return;
    const handle = ev.currentTarget as HTMLElement;
    const rowEl = handle.closest("[data-sortable-index]") as HTMLElement | null;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    if (!rowEl || !listEl) return;
    ev.preventDefault();
    try {
      handle.setPointerCapture(ev.pointerId);
    } catch {
      // Headless test environments may omit setPointerCapture.
    }
    activeDrag = {
      listId: opts.listId,
      pointerId: ev.pointerId,
      orientation: opts.orientation,
      fromIndex: opts.idx,
      overIndex: opts.idx,
      insertAfter: false,
    };
    clearDragDomClasses(listEl);
    rowEl.classList.add("dragging");
  };

  const onPointerMove = (ev: PointerEvent): void => {
    if (!activeDrag || activeDrag.listId !== opts.listId || activeDrag.pointerId !== ev.pointerId) {
      return;
    }
    const handle = ev.currentTarget as HTMLElement;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    if (!listEl) return;

    const rows = Array.from(listEl.querySelectorAll<HTMLElement>(":scope > [data-sortable-index]"));
    if (!rows.length) return;

    const isRtl =
      opts.orientation === "horizontal" &&
      typeof getComputedStyle === "function" &&
      getComputedStyle(listEl).direction === "rtl";

    let bestRow: HTMLElement | null = null;
    let bestIdx = activeDrag.fromIndex;
    let bestDist = Infinity;
    let bestAfter = false;

    for (const r of rows) {
      const rIdx = Number(r.dataset.sortableIndex);
      if (!Number.isFinite(rIdx)) continue;
      const rect = r.getBoundingClientRect();
      if (!rect.width && !rect.height) continue;
      if (opts.orientation === "vertical") {
        const midY = rect.top + rect.height / 2;
        const dist = Math.abs(ev.clientY - midY);
        if (dist < bestDist) {
          bestDist = dist;
          bestRow = r;
          bestIdx = rIdx;
          bestAfter = ev.clientY > midY;
        }
      } else {
        const midX = rect.left + rect.width / 2;
        const midY = rect.top + rect.height / 2;
        const dist = Math.hypot(ev.clientX - midX, (ev.clientY - midY) * 1.5);
        if (dist < bestDist) {
          bestDist = dist;
          bestRow = r;
          bestIdx = rIdx;
          bestAfter = isRtl ? ev.clientX < midX : ev.clientX > midX;
        }
      }
    }

    activeDrag.overIndex = bestIdx;
    activeDrag.insertAfter = bestAfter;
    for (const r of rows) {
      r.classList.remove("drag-over-before", "drag-over-after");
    }
    if (bestRow && bestIdx !== activeDrag.fromIndex) {
      bestRow.classList.add(bestAfter ? "drag-over-after" : "drag-over-before");
    }
  };

  const finishDrag = (ev: PointerEvent, cancelled: boolean): void => {
    if (!activeDrag || activeDrag.listId !== opts.listId || activeDrag.pointerId !== ev.pointerId) {
      return;
    }
    const session = activeDrag;
    activeDrag = null;
    const handle = ev.currentTarget as HTMLElement;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    try {
      if (typeof handle.hasPointerCapture === "function" && handle.hasPointerCapture(ev.pointerId)) {
        handle.releasePointerCapture(ev.pointerId);
      }
    } catch {
      // Ignore release errors.
    }
    clearDragDomClasses(listEl);
    if (cancelled) return;
    const toIndex = computeDropTargetIndex(
      session.fromIndex,
      session.overIndex,
      session.insertAfter,
      opts.total,
    );
    if (toIndex !== session.fromIndex) {
      opts.onReorder(session.fromIndex, toIndex);
      announceReorder(opts.listId, opts.itemLabel, toIndex, opts.total, opts.overlay, handle);
    }
  };

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp: (ev: PointerEvent) => finishDrag(ev, false),
    onPointerCancel: (ev: PointerEvent) => finishDrag(ev, true),
  };
}

function triggerKeyboardMoveWithFocusRestore(opts: {
  btnEl: HTMLElement;
  listId: string;
  itemKey: string;
  itemLabel: string;
  preferredDir: "prev" | "next";
  fromIndex: number;
  toIndex: number;
  total: number;
  overlay?: Readonly<Record<string, string>> | null;
  onReorder: (fromIndex: number, toIndex: number) => void;
}): void {
  const root =
    typeof opts.btnEl.getRootNode === "function"
      ? (opts.btnEl.getRootNode() as Document | ShadowRoot)
      : document;
  opts.onReorder(opts.fromIndex, opts.toIndex);
  announceReorder(opts.listId, opts.itemLabel, opts.toIndex, opts.total, opts.overlay, opts.btnEl);

  requestAnimationFrame(() => {
    if (!root || typeof root.querySelector !== "function") return;
    const listEl = root.querySelector(`[data-sortable-list="${CSS.escape(opts.listId)}"]`);
    if (!listEl) return;
    const itemEl = listEl.querySelector(
      `[data-sortable-key="${CSS.escape(opts.itemKey)}"]`,
    ) as HTMLElement | null;
    if (!itemEl) return;
    const sameBtn = itemEl.querySelector(
      `button[data-move-dir="${opts.preferredDir}"]:not(:disabled)`,
    ) as HTMLButtonElement | null;
    if (sameBtn) {
      sameBtn.focus({ preventScroll: true });
      return;
    }
    const altBtn = itemEl.querySelector(
      "button[data-move-dir]:not(:disabled), button:not(:disabled)",
    ) as HTMLButtonElement | null;
    altBtn?.focus({ preventScroll: true });
  });
}

export interface SortableListOptions<T> {
  id: string;
  items: readonly T[];
  getKey: (item: T, index: number) => string;
  getLabel: (item: T, index: number) => string;
  renderContent: (item: T, index: number) => unknown;
  renderActions?: (item: T, index: number) => unknown;
  onReorder: (fromIndex: number, toIndex: number) => void;
  ariaLabel?: string;
  rowClass?: string | ((item: T, index: number) => string);
  canMoveItem?: (item: T, index: number) => boolean;
  emptyState?: TemplateResult | string;
  overlay?: Readonly<Record<string, string>> | null;
}

export function renderSortableList<T>(opts: SortableListOptions<T>): TemplateResult {
  const total = opts.items.length;
  const liveMsg = SORTABLE_LIVE_STATUS.get(opts.id) || "";

  if (total === 0) {
    return html`<div id=${opts.id} data-sortable-list=${opts.id} class="sortable-list">
      ${typeof opts.emptyState === "string"
        ? html`<p class="empty-state">${opts.emptyState}</p>`
        : opts.emptyState || nothing}
      <span data-sortable-live role="status" aria-live="polite" class="sr-only">${liveMsg}</span>
    </div>`;
  }

  return html`<div
    id=${opts.id}
    data-sortable-list=${opts.id}
    role="group"
    aria-label=${opts.ariaLabel || nothing}
    class="sortable-list"
  >
    ${repeat(
      opts.items,
      (item, idx) => opts.getKey(item, idx),
      (item, idx) => {
        const key = opts.getKey(item, idx);
        const label = opts.getLabel(item, idx);
        const movable = opts.canMoveItem ? opts.canMoveItem(item, idx) : true;
        const extraCls =
          typeof opts.rowClass === "function"
            ? opts.rowClass(item, idx)
            : opts.rowClass || "";
        const drag = attachDragHandleHandlers({
          listId: opts.id,
          orientation: "vertical",
          idx,
          total,
          itemLabel: label,
          overlay: opts.overlay,
          onReorder: opts.onReorder,
        });

        return html`<div
          data-sortable-key=${key}
          data-sortable-index=${String(idx)}
          class="sortable-row${extraCls ? ` ${extraCls}` : ""}"
        >
          ${movable && total > 1
            ? html`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                title=${t("action.drag_reorder", { item: label }, opts.overlay)}
                @pointerdown=${drag.onPointerDown}
                @pointermove=${drag.onPointerMove}
                @pointerup=${drag.onPointerUp}
                @pointercancel=${drag.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`
            : nothing}
          <div class="sortable-row-content">${opts.renderContent(item, idx)}</div>
          <div class="sortable-row-actions">
            ${movable && total > 1
              ? html`<button
                    type="button"
                    data-move-dir="prev"
                    aria-label=${t("action.move_up", { item: label }, opts.overlay)}
                    ?disabled=${idx === 0}
                    @click=${(ev: Event) =>
                      triggerKeyboardMoveWithFocusRestore({
                        btnEl: ev.currentTarget as HTMLElement,
                        listId: opts.id,
                        itemKey: key,
                        itemLabel: label,
                        preferredDir: "prev",
                        fromIndex: idx,
                        toIndex: idx - 1,
                        total,
                        overlay: opts.overlay,
                        onReorder: opts.onReorder,
                      })}
                    class="btn-icon"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    data-move-dir="next"
                    aria-label=${t("action.move_down", { item: label }, opts.overlay)}
                    ?disabled=${idx === total - 1}
                    @click=${(ev: Event) =>
                      triggerKeyboardMoveWithFocusRestore({
                        btnEl: ev.currentTarget as HTMLElement,
                        listId: opts.id,
                        itemKey: key,
                        itemLabel: label,
                        preferredDir: "next",
                        fromIndex: idx,
                        toIndex: idx + 1,
                        total,
                        overlay: opts.overlay,
                        onReorder: opts.onReorder,
                      })}
                    class="btn-icon"
                  >
                    ↓
                  </button>`
              : nothing}
            ${opts.renderActions ? opts.renderActions(item, idx) : nothing}
          </div>
        </div>`;
      },
    )}
    <span data-sortable-live role="status" aria-live="polite" class="sr-only">${liveMsg}</span>
  </div>`;
}

export interface PillListItem {
  token: string;
  label: string;
  enabled: boolean;
  disabled?: boolean;
}

export interface PillListOptions {
  id: string;
  ariaLabel?: string;
  items: readonly PillListItem[];
  onToggle: (token: string, nextEnabled: boolean) => void;
  onReorder?: (fromEnabledIndex: number, toEnabledIndex: number) => void;
  overlay?: Readonly<Record<string, string>> | null;
}

export function renderPillList(opts: PillListOptions): TemplateResult {
  const enabledItems = opts.items.filter((it) => it.enabled);
  const disabledItems = opts.items.filter((it) => !it.enabled);
  const enabledCount = enabledItems.length;
  const canReorder = Boolean(opts.onReorder && enabledCount > 1);
  const liveMsg = SORTABLE_LIVE_STATUS.get(opts.id) || "";

  return html`<div
    id=${opts.id}
    data-sortable-list=${opts.id}
    role="group"
    aria-label=${opts.ariaLabel || nothing}
    class="pill-list"
  >
    ${repeat(
      enabledItems,
      (item) => item.token,
      (item, idx) => {
        const drag = opts.onReorder
          ? attachDragHandleHandlers({
              listId: opts.id,
              orientation: "horizontal",
              idx,
              total: enabledCount,
              itemLabel: item.label,
              overlay: opts.overlay,
              onReorder: opts.onReorder,
            })
          : null;

        return html`<span
          data-sortable-key=${item.token}
          data-sortable-index=${canReorder ? String(idx) : nothing}
          class="pill enabled"
        >
          ${canReorder && drag
            ? html`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                title=${t("action.drag_reorder", { item: item.label }, opts.overlay)}
                @pointerdown=${drag.onPointerDown}
                @pointermove=${drag.onPointerMove}
                @pointerup=${drag.onPointerUp}
                @pointercancel=${drag.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`
            : nothing}
          ${canReorder && opts.onReorder
            ? html`<button
                type="button"
                data-move-dir="prev"
                aria-label=${t("action.move_earlier", { item: item.label }, opts.overlay)}
                ?disabled=${idx === 0}
                @click=${(ev: Event) =>
                  triggerKeyboardMoveWithFocusRestore({
                    btnEl: ev.currentTarget as HTMLElement,
                    listId: opts.id,
                    itemKey: item.token,
                    itemLabel: item.label,
                    preferredDir: "prev",
                    fromIndex: idx,
                    toIndex: idx - 1,
                    total: enabledCount,
                    overlay: opts.overlay,
                    onReorder: opts.onReorder!,
                  })}
                class="pill-move"
              >
                ‹
              </button>`
            : nothing}
          <button
            type="button"
            aria-pressed="true"
            ?disabled=${Boolean(item.disabled)}
            @click=${() => opts.onToggle(item.token, false)}
            class="pill-toggle"
          >
            ${item.label}
          </button>
          ${canReorder && opts.onReorder
            ? html`<button
                type="button"
                data-move-dir="next"
                aria-label=${t("action.move_later", { item: item.label }, opts.overlay)}
                ?disabled=${idx === enabledCount - 1}
                @click=${(ev: Event) =>
                  triggerKeyboardMoveWithFocusRestore({
                    btnEl: ev.currentTarget as HTMLElement,
                    listId: opts.id,
                    itemKey: item.token,
                    itemLabel: item.label,
                    preferredDir: "next",
                    fromIndex: idx,
                    toIndex: idx + 1,
                    total: enabledCount,
                    overlay: opts.overlay,
                    onReorder: opts.onReorder!,
                  })}
                class="pill-move"
              >
                ›
              </button>`
            : nothing}
        </span>`;
      },
    )}
    ${repeat(
      disabledItems,
      (item) => `off:${item.token}`,
      (item) => html`<span class="pill">
        <button
          type="button"
          aria-pressed="false"
          ?disabled=${Boolean(item.disabled)}
          @click=${() => opts.onToggle(item.token, true)}
          class="pill-toggle"
        >
          ${item.label}
        </button>
      </span>`,
    )}
    <span data-sortable-live role="status" aria-live="polite" class="sr-only">${liveMsg}</span>
  </div>`;
}

// ---------------------------------------------------------------------------
// Entity Slot Lists, Select Options, Icons, Table Sort Headers & Pref/Native Rows
// ---------------------------------------------------------------------------

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
  useCombobox?: boolean;
  host?: { requestUpdate(): void } | null;
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

  const renderSlotField = (val: string, idx: number): TemplateResult => html`<div
    class="stacked-field list-row-grow"
  >
    ${opts.slotLabel ? html`<span class="field-label">${opts.slotLabel(idx)}</span>` : nothing}
    ${opts.useCombobox
      ? renderEntityCombobox({
          id: `${opts.id}-combo-${idx}`,
          value: val,
          options: opts.choices,
          ariaLabel: opts.selectAriaLabel,
          emptyOptionLabel: opts.emptyOptionLabel,
          host: opts.host,
          onChange: (nextVal) => opts.onChange(idx, nextVal),
        })
      : html`<select
          aria-label=${opts.selectAriaLabel}
          .value=${val}
          @change=${(ev: Event) =>
            opts.onChange(idx, (ev.currentTarget as HTMLSelectElement).value)}
        >
          ${renderSelectOptions(opts.choices, val, opts.emptyOptionLabel)}
        </select>`}
  </div>`;

  if (opts.onReorder) {
    return renderSortableList({
      id: opts.id,
      items: opts.items,
      getKey: (val, idx) => (val ? `ent:${val}:${idx}` : `empty:${idx}`),
      getLabel: (val, idx) =>
        opts.slotLabel ? opts.slotLabel(idx) : val || `${opts.selectAriaLabel} ${idx + 1}`,
      onReorder: opts.onReorder,
      renderContent: (val, idx) => renderSlotField(val, idx),
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

export function renderSvgIcon(pathD: string): TemplateResult {
  return html`<svg viewBox="0 0 24 24" aria-hidden="true"><path d=${pathD}></path></svg>`;
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
  const indicator = isActive ? (store.deviceSortAsc ? " ▲" : " ▼") : "";
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
    <button type="button" @click=${onSort} class="sort-btn">${label}<span aria-hidden="true">${indicator}</span></button>
  </th>`;
}

function getLocaleOverlay(store: StudioStore): Readonly<Record<string, string>> | null {
  const stateAny = store.state as (Record<string, unknown> | null | undefined);
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
        void store.entity.espAction(item.entity_id, checked ? "turn_on" : "turn_off", checked ? "on" : "off");
      }
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
      const nextVal = (ev.currentTarget as HTMLSelectElement).value;
      if (prefKey) {
        store.entity.stageDeviceSetting(prefKey, nextVal);
      } else {
        void store.entity.espSelect(item.entity_id, nextVal);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${st} @change=${onChange}>
        ${opts.map(
          (opt) =>
            html`<option value=${opt} ?selected=${opt === st}>
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
        .checked=${isOn}
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
      control: html`<select aria-label=${label} .value=${st} @change=${onChange}>
        ${opts.map(
          (opt) =>
            html`<option value=${opt} ?selected=${opt === st}>
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
    ? item.entity_id.split(".", 2)[1].toLowerCase()
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
    idTail.endsWith("_restart_device") ||
    idTail.endsWith("_restart")
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
  return [...items].sort((a, b) => {
    const ra = QUICK_ACTION_RANK[quickActionKind(a)];
    const rb = QUICK_ACTION_RANK[quickActionKind(b)];
    if (ra !== rb) return ra - rb;
    return `${a.name || ""} ${a.entity_id}`
      .toLowerCase()
      .localeCompare(`${b.name || ""} ${b.entity_id}`.toLowerCase());
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
