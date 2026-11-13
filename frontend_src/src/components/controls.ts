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
  const prefKey = item.pref_key || "";
  const unavailable = !prefKey && (st === "unavailable" || st === "unknown");

  if (dom === "switch") {
    const isOn = st === "on";
    const onToggle = (ev: Event): void => {
      const checked = (ev.currentTarget as HTMLInputElement).checked;
      if (prefKey) {
        store.stageDeviceSetting(prefKey, checked);
      } else {
        void store.espAction(item.entity_id, checked ? "turn_on" : "turn_off", checked ? "on" : "off");
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
        store.stageDeviceSetting(prefKey, nextVal);
      } else {
        void store.espSelect(item.entity_id, nextVal);
      }
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
        if (prefKey) {
          store.stageDeviceSetting(prefKey, raw);
        } else {
          void store.espNumber(item.entity_id, raw);
        }
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
    const onRun = (): void => {
      if (item.device_command) {
        void store.runDeviceAction(item.device_command, toastMsg);
      } else {
        void store.espAction(item.entity_id, "press", undefined, toastMsg);
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
): TemplateResult | typeof nothing {
  if (!buttons.length) return nothing;
  const ordered = sortQuickActionButtons(buttons);
  return html`<div class="quick-action-grid" role="group" aria-label="Device Quick Actions">
    ${ordered.map((item) => {
      const kind = quickActionKind(item);
      const label = entityLabel(item.name || item.entity_id);
      const buttonUnavailable = String(item.state ?? "") === "unavailable";
      const toastMsg =
        kind === "restart"
          ? "Restarting Device…"
          : kind === "hibernate"
            ? "Hibernating Device…"
            : `Triggered "${label}"`;
      const onTrigger = (): void => {
        if (item.device_command) {
          void store.runDeviceAction(item.device_command, toastMsg);
        } else {
          void store.espAction(item.entity_id, "press", undefined, toastMsg);
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
