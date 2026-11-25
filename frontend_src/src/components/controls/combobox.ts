/**
 * Reusable WAI-ARIA 1.2 Searchable Entity Combobox (`components/controls/combobox.ts`, `D-062`).
 */

import { t } from "../../i18n/index.js";
import { focusSafe, html, live, nothing, repeat, type TemplateResult } from "../../lib/lit.js";

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
    const objIdLow = idLow.includes(".") ? (idLow.split(".", 2)[1] ?? idLow) : idLow;
    const nameLow = String(item.name || item.id || "").toLowerCase();
    const areaLow = String(item.area_name || "").toLowerCase();
    const domLow = String(
      item.domain || (idLow.includes(".") ? (idLow.split(".", 1)[0] ?? "") : ""),
    ).toLowerCase();
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
      } else if (
        nameLow.startsWith(query) ||
        objIdLow.startsWith(query) ||
        idLow.startsWith(query)
      ) {
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

  const matched = ui.open
    ? matchComboboxOptions(allOptions, ui.query, maxResults)
    : { items: [] as ComboboxOptionItem[], totalMatches: 0 };
  const matchedItems = matched.items;
  const totalMatches = matched.totalMatches;
  const clampedActiveIdx =
    ui.open && matchedItems.length > 0
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
    const cap = Math.max(1, maxResults);
    const curIdx = curVal
      ? allOptions.slice(0, cap).findIndex((o) => o.id === curVal)
      : -1;
    ui.activeIndex = curIdx >= 0 ? curIdx : 0;
    notifyUi(sourceEl);
  };

  const onInput = (ev: Event): void => {
    const inp = ev.currentTarget as HTMLInputElement;
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
        const visibleCount = Math.min(allOptions.length, Math.max(1, maxResults));
        ui.activeIndex = Math.max(0, visibleCount - 1);
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
        const activeItem = clampedActiveIdx >= 0 ? matchedItems[clampedActiveIdx] : undefined;
        if (activeItem) {
          commitSelection(activeItem.id, inp);
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
        .value=${ui.open ? focusSafe(ui.query) : live(closedDisplayValue)}
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
      ${ui.open
        ? html`${matchedItems.length === 0
              ? html`<li role="presentation" class="combobox-empty">
                  ${t("combobox.no_matches", undefined, opts.overlay)}
                </li>`
              : repeat(
                  matchedItems,
                  (item) => item.id,
                  (item, idx) => {
                    const dom =
                      item.domain || (item.id.includes(".") ? (item.id.split(".", 1)[0] ?? "") : "");
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
              : nothing}`
        : nothing}
    </ul>
  </div>`;
}
