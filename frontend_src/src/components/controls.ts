/**
 * Shared Lit UI controls, native ESPHome entity rows, and table header components.
 * Note: Event bindings (`@click`, `@change`) always precede `class="..."` / `role="radio"` attributes.
 */

import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { CatalogChoice, EspHomeEntityItem } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

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
    return html`<div class="settings-row">
      <div class="settings-row-text"><span class="row-label">${label}</span></div>
      <div class="settings-row-control">
        <input
          type="checkbox"
          role="switch"
          aria-label=${label}
          ?disabled=${unavailable}
          .checked=${isOn}
          @change=${onToggle}
          class="switch"
        />
      </div>
    </div>`;
  }

  if (dom === "select") {
    const opts = item.options || [];
    const onChange = (ev: Event): void => {
      const next = (ev.currentTarget as HTMLSelectElement).value;
      void store.espSelect(item.entity_id, next);
    };
    return html`<div class="settings-row">
      <div class="settings-row-text"><span class="row-label">${label}</span></div>
      <div class="settings-row-control">
        <select aria-label=${label} ?disabled=${unavailable} .value=${st} @change=${onChange}>
          ${opts.map((opt) => html`<option value=${opt} ?selected=${opt === st}>${opt}</option>`)}
        </select>
      </div>
    </div>`;
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
      return html`<div class="settings-row">
        <div class="settings-row-text"><span class="row-label">${label}</span></div>
        <div class="settings-row-control">
          <span class="kv-value">${fmtNumber(numVal, store.hass)}${unitSuffix}</span>
          <input
            type="range"
            aria-label=${label}
            min=${String(min)}
            max=${String(max)}
            step=${String(step)}
            ?disabled=${unavailable}
            .value=${String(numVal)}
            @change=${onCommit}
          />
        </div>
      </div>`;
    }
    return html`<div class="settings-row">
      <div class="settings-row-text"><span class="row-label">${label}</span></div>
      <div class="settings-row-control">
        <input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          ?disabled=${unavailable}
          .value=${String(numVal)}
          @change=${onCommit}
        />
        ${item.unit ? html`<span class="help-text">${item.unit}</span>` : nothing}
      </div>
    </div>`;
  }

  if (dom === "button") {
    const onPress = (): void => {
      void store.espAction(item.entity_id, "press");
    };
    return html`<div class="settings-row">
      <div class="settings-row-text"><span class="row-label">${label}</span></div>
      <div class="settings-row-control">
        <button type="button" ?disabled=${unavailable} @click=${onPress} class="btn btn-secondary btn-compact">
          Run
        </button>
      </div>
    </div>`;
  }

  if (dom === "update") {
    const hasUpdate = st === "on";
    const onInstall = (): void => {
      void store.espAction(item.entity_id, "install");
    };
    return html`<div class="settings-row">
      <div class="settings-row-text"><span class="row-label">${label}</span></div>
      <div class="settings-row-control">
        <span class="chip ${hasUpdate ? "chip-warning" : ""}">${hasUpdate ? "Update available" : "Up to date"}</span>
        ${hasUpdate
          ? html`<button type="button" @click=${onInstall} class="btn btn-primary btn-compact">Install</button>`
          : nothing}
      </div>
    </div>`;
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
