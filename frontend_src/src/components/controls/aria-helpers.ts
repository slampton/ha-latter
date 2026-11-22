/**
 * Shared WAI-ARIA description wiring, SVG icon helpers, select option renderer,
 * table sort header, & Device 12/24h time helper (`components/controls/aria-helpers.ts`).
 */

import {
  Directive,
  directive,
  html,
  live,
  noChange,
  nothing,
  PartType,
  type ElementPart,
  type PartInfo,
  type TemplateResult,
} from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { CatalogChoice } from "../../types.js";
import { defaultLocaleTimeFormat } from "../../utils/format.js";

export function isDeviceTime24h(store: StudioStore): boolean {
  if (store.currentScope !== "system") {
    const raw =
      store.entity.getPref("time_format")?.value ??
      store.state?.config?.time_format;
    const trimmed = raw !== undefined && raw !== null ? String(raw).trim() : "";
    if (trimmed) {
      return trimmed.startsWith("24");
    }
  }
  return defaultLocaleTimeFormat(store.hass).startsWith("24");
}

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

export const autoWireDescribedBy = directive(AutoDescribeDirective);

export function renderSelectOptions(
  choices: readonly CatalogChoice[] | undefined,
  selectedId: string | null | undefined,
  emptyOptionLabel = "None",
): TemplateResult[] {
  const cur = String(selectedId || "");
  const list = choices || [];
  const hasSelected = !cur || list.some((c) => c.id === cur);
  const out: TemplateResult[] = [
    html`<option value="" .selected=${live(cur === "")}>${emptyOptionLabel}</option>`,
  ];
  if (cur && !hasSelected) {
    out.push(html`<option value=${cur} .selected=${live(true)}>${cur} (missing)</option>`);
  }
  for (const item of list) {
    out.push(
      html`<option value=${item.id} .selected=${live(item.id === cur)}>${item.name || item.id}</option>`,
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
