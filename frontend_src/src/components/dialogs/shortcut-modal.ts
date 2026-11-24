/**
 * Add / Edit Shortcut Modal (`#latter-shortcut-modal`, `D-047`, `D-062`, `D-080`).
 * - Short-circuits closed `<dialog>` body
 * - Roving-arrow `tablist` + `tabpanel` for Shortcut type
 * - WAI-ARIA `renderEntityCombobox` replacing unbounded entity `<select>` menus
 * - Accessible MDI icon picker with weight filter (`All` | `Solid` | `Outline`),
 *   smart-home synonym search, and live-styled badge style + semantic accent controls
 * - `focusSafe` text inputs
 */

import {
  MAX_PINNED_GRID_PAGES,
  NATIVE_DOCK_APP_TOKENS,
  SHORTCUT_ACCENTS_CATALOG,
  SHORTCUT_BADGE_STYLES_CATALOG,
  SHORTCUT_LABEL_MAX,
  SHORTCUT_ROUTES_CATALOG,
} from "../../constants.js";
import { formatHaEntityState, type StudioTranslationKey } from "../../i18n/index.js";
import { focusSafe, html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import {
  isKnownMdiIcon,
  isMdiCatalogLoaded,
  MDI_TOTAL_ICON_COUNT,
  type MdiIconStyleFilter,
  normalizeMdiIconSlug,
  ROUTE_PREVIEW_ICONS,
  searchMdiIcons,
  SHORTCUT_DOMAIN_ACTIONS,
  SHORTCUT_DOMAIN_LABELS,
} from "../../mdi-catalog.js";
import {
  isCatalogItemSupported,
  shortcutBadgeClass,
  type StudioStore,
} from "../../state/store.js";
import type { ShortcutAccent, ShortcutBadgeStyle } from "../../types.js";
import { fmtNumber } from "../../utils/format.js";
import {
  canPlaceTile,
  resolveDeviceGridDims,
  resolveTileGridLayout,
} from "../../utils/tile-grid.js";
import {
  type ComboboxOptionItem,
  renderEntityCombobox,
  renderSwitchRow,
} from "../controls.js";

const hoveredSpanByStore = new WeakMap<StudioStore, { w: number; h: number }>();

const ICON_STYLE_OPTIONS: ReadonlyArray<{
  value: MdiIconStyleFilter;
  labelKey: StudioTranslationKey;
}> = [
  { value: "all", labelKey: "dialogs.sc_icon_style_all" },
  { value: "solid", labelKey: "dialogs.sc_icon_style_solid" },
  { value: "outline", labelKey: "dialogs.sc_icon_style_outline" },
];

const BADGE_STYLE_LABEL_KEYS: Readonly<Record<string, StudioTranslationKey>> = {
  glass: "dialogs.sc_badge_style_glass",
  inverted: "dialogs.sc_badge_style_inverted",
};

const ACCENT_LABEL_KEYS: Readonly<Record<string, StudioTranslationKey>> = {
  default: "dialogs.sc_accent_default",
  primary: "dialogs.sc_accent_primary",
  gold: "dialogs.sc_accent_gold",
  green: "dialogs.sc_accent_green",
  red: "dialogs.sc_accent_red",
  orange: "dialogs.sc_accent_orange",
};

interface CachedMdiSearch {
  queryKey: string;
  styleFilter: MdiIconStyleFilter;
  loaded: boolean;
  items: readonly string[];
  totalMatches: number;
}

let mdiSearchCache: CachedMdiSearch | null = null;

function getCachedMdiSearch(
  rawQuery: string,
  styleFilter: MdiIconStyleFilter,
): { items: readonly string[]; totalMatches: number } {
  const queryKey = String(rawQuery || "").trim().toLowerCase();
  const loaded = isMdiCatalogLoaded();
  if (
    mdiSearchCache &&
    mdiSearchCache.queryKey === queryKey &&
    mdiSearchCache.styleFilter === styleFilter &&
    mdiSearchCache.loaded === loaded
  ) {
    return { items: mdiSearchCache.items, totalMatches: mdiSearchCache.totalMatches };
  }
  const result = searchMdiIcons(rawQuery, 120, styleFilter);
  mdiSearchCache = {
    queryKey,
    styleFilter,
    loaded,
    items: result.items,
    totalMatches: result.totalMatches,
  };
  return result;
}

function handleRadioGroupKeyDown<T extends string>(
  ev: KeyboardEvent,
  values: ReadonlyArray<T>,
  current: T,
  onSelect: (nextVal: T) => void,
  idPrefix: string,
): void {
  if (
    ev.key !== "ArrowLeft" &&
    ev.key !== "ArrowRight" &&
    ev.key !== "ArrowUp" &&
    ev.key !== "ArrowDown" &&
    ev.key !== "Home" &&
    ev.key !== "End"
  ) {
    return;
  }
  ev.preventDefault();
  const curIdx = Math.max(0, values.indexOf(current));
  let nextIdx = curIdx;
  if (ev.key === "Home") {
    nextIdx = 0;
  } else if (ev.key === "End") {
    nextIdx = values.length - 1;
  } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
    nextIdx = (curIdx - 1 + values.length) % values.length;
  } else {
    nextIdx = (curIdx + 1) % values.length;
  }
  const nextVal = values[nextIdx];
  if (nextVal === undefined) return;
  onSelect(nextVal);
  const groupEl = (ev.currentTarget as HTMLElement).parentElement;
  const targetId = `#${idPrefix}${nextVal || "default"}`;
  requestAnimationFrame(() => {
    const nextBtn = groupEl?.querySelector(targetId) as HTMLElement | null;
    nextBtn?.focus();
  });
}

function humanizeMdiIconLabel(slug: string): string {
  const clean = slug.startsWith("mdi:") ? slug.slice(4) : slug;
  const words = clean.replace(/[-_]+/g, " ").trim();
  if (!words) return slug;
  const sentence = words.charAt(0).toUpperCase() + words.slice(1);
  return `${sentence} (${slug})`;
}

export function renderShortcutDialog(store: StudioStore): TemplateResult {
  const scModal = store.shortcutModal;
  const close = (): void => store.entity.closeShortcutModal();

  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget) {
      close();
    }
  };

  if (!scModal.open) {
    return html`<dialog
      id="latter-shortcut-modal"
      aria-labelledby="latter-shortcut-title"
      @cancel=${close}
      @click=${onBackdropClick}
      class="studio-dialog shortcut-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const scIsDock = scModal.listKey === "dock_items";
  const scTitle =
    scModal.editIndex !== null
      ? scIsDock
        ? store.t("dialogs.sc_edit_dock")
        : store.t("dialogs.sc_edit_pinned")
      : scIsDock
        ? store.t("dialogs.sc_add_dock")
        : store.t("dialogs.sc_add_pinned");

  const devCaps = store.state?.capabilities;
  const availableRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!scIsDock && r.dockOnly) return false;
    if (scIsDock && (r.token === "settings:root" || NATIVE_DOCK_APP_TOKENS.includes(r.token))) {
      return false;
    }
    return isCatalogItemSupported(r, devCaps);
  });

  const routeGroups: Array<{ group: string; items: typeof availableRoutes }> = [];
  for (const r of availableRoutes) {
    const grpName = r.group || "Apps";
    const existingGrp = routeGroups.find((g) => g.group === grpName);
    if (existingGrp) {
      existingGrp.items.push(r);
    } else {
      routeGroups.push({ group: grpName, items: [r] });
    }
  }

  const allShortcutEntities = store.state?.catalog?.shortcut_entities || [];
  const availableDomains = Array.from(
    new Set(allShortcutEntities.map((e) => e.domain)),
  ).sort();
  const domainFilteredEntities = allShortcutEntities.filter(
    (e) => scModal.entityDomainFilter === "all" || e.domain === scModal.entityDomainFilter,
  );
  const comboboxOptions: ComboboxOptionItem[] = domainFilteredEntities.map((e) => {
    const stateLbl = formatHaEntityState(store.hass, e.id);
    return {
      id: e.id,
      name: e.name,
      domain: e.domain,
      area_name: e.area_name,
      icon: e.icon,
      state_label: stateLbl || undefined,
    };
  });

  const selectedEntityObj =
    allShortcutEntities.find((e) => e.id === scModal.entityTarget) || null;
  const selectedEntityDomain = selectedEntityObj
    ? selectedEntityObj.domain
    : scModal.entityTarget.split(".", 1)[0] || "";
  const availableEntityActions = SHORTCUT_DOMAIN_ACTIONS[selectedEntityDomain] || [];

  const effectiveRouteTarget = availableRoutes.some((r) => r.token === scModal.routeTarget)
    ? scModal.routeTarget
    : availableRoutes[0]?.token || scModal.routeTarget;
  const selectedRouteSpec =
    availableRoutes.find((r) => r.token === effectiveRouteTarget) ||
    SHORTCUT_ROUTES_CATALOG.find((r) => r.token === effectiveRouteTarget);

  const autoDefaultLabel =
    scModal.kind === "route"
      ? selectedRouteSpec?.label || store.t("dialogs.sc_default_shortcut")
      : selectedEntityObj?.name ||
        scModal.entityTarget ||
        store.t("dialogs.sc_default_entity_action");
  const autoDefaultIcon =
    scModal.kind === "route"
      ? ROUTE_PREVIEW_ICONS[effectiveRouteTarget] || "mdi:apps"
      : selectedEntityObj?.icon || "mdi:flash";

  const selectedCustomIcon = normalizeMdiIconSlug(scModal.icon);
  const typedSearchIcon = normalizeMdiIconSlug(scModal.iconSearch);
  const previewIcon =
    selectedCustomIcon ||
    (isKnownMdiIcon(typedSearchIcon) ? typedSearchIcon : autoDefaultIcon);
  const hasIconQuery = scModal.iconSearch.trim().length > 0;
  const { items: filteredMdiIcons, totalMatches: mdiMatchCount } = getCachedMdiSearch(
    scModal.iconSearch,
    scModal.iconStyleFilter,
  );
  const totalIconsText = fmtNumber(MDI_TOTAL_ICON_COUNT, store.hass, 0);
  const previewBadgeClass = shortcutBadgeClass(scModal.badgeStyle, scModal.accent);
  const iconStyleValues = ICON_STYLE_OPTIONS.map((o) => o.value);
  const badgeStyleTokens = SHORTCUT_BADGE_STYLES_CATALOG.map((o) => o.token);
  const activeBadgeStyleToken = scModal.badgeStyle === "inverted" ? "inverted" : "glass";
  const accentTokens = SHORTCUT_ACCENTS_CATALOG.map((o) => o.token);
  const activeAccentToken = scModal.accent || "default";

  const setIconStyleFilter = (nextFilter: MdiIconStyleFilter): void => {
    store.shortcutModal = { ...store.shortcutModal, iconStyleFilter: nextFilter };
    store.host.requestUpdate();
  };

  const setBadgeStyleToken = (token: string): void => {
    const nextStyle: ShortcutBadgeStyle = token === "inverted" ? "inverted" : "";
    store.shortcutModal = { ...store.shortcutModal, badgeStyle: nextStyle };
    store.host.requestUpdate();
  };

  const setAccentToken = (token: string): void => {
    const nextAccent: ShortcutAccent =
      token === "default" ? "" : (token as ShortcutAccent);
    store.shortcutModal = { ...store.shortcutModal, accent: nextAccent };
    store.host.requestUpdate();
  };

  const setShortcutKind = (nextKind: "route" | "entity", focusTabEl?: HTMLElement | null): void => {
    store.shortcutModal = { ...store.shortcutModal, kind: nextKind };
    store.host.requestUpdate();
    if (focusTabEl) {
      requestAnimationFrame(() => {
        focusTabEl.focus();
      });
    }
  };

  const onTypeTabKeyDown = (ev: KeyboardEvent): void => {
    if (
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight" &&
      ev.key !== "Home" &&
      ev.key !== "End"
    ) {
      return;
    }
    ev.preventDefault();
    let nextKind: "route" | "entity";
    if (ev.key === "Home") {
      nextKind = "route";
    } else if (ev.key === "End") {
      nextKind = "entity";
    } else {
      nextKind = scModal.kind === "route" ? "entity" : "route";
    }
    const tablist = (ev.currentTarget as HTMLElement).parentElement;
    const targetBtn = tablist?.querySelector(
      nextKind === "route" ? "#shortcut-tab-route" : "#shortcut-tab-entity",
    ) as HTMLElement | null;
    setShortcutKind(nextKind, targetBtn);
  };

  const isRouteTab = scModal.kind === "route";

  return html`<dialog
    id="latter-shortcut-modal"
    aria-labelledby="latter-shortcut-title"
    @cancel=${close}
    @click=${onBackdropClick}
    class="studio-dialog shortcut-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-shortcut-title" class="dialog-title">${scTitle}</h3>

      <div role="tablist" aria-label=${store.t("dialogs.sc_type_aria")} class="scope-tabs">
        <button
          type="button"
          id="shortcut-tab-route"
          role="tab"
          aria-selected=${isRouteTab ? "true" : "false"}
          aria-controls="shortcut-tabpanel"
          tabindex=${isRouteTab ? "0" : "-1"}
          @click=${() => setShortcutKind("route")}
          @keydown=${onTypeTabKeyDown}
          class="scope-tab ${isRouteTab ? "active" : ""}"
        >
          ${scIsDock ? store.t("dialogs.sc_tab_subpage") : store.t("dialogs.sc_tab_app_page")}
        </button>
        <button
          type="button"
          id="shortcut-tab-entity"
          role="tab"
          aria-selected=${!isRouteTab ? "true" : "false"}
          aria-controls="shortcut-tabpanel"
          tabindex=${!isRouteTab ? "0" : "-1"}
          @click=${() => setShortcutKind("entity")}
          @keydown=${onTypeTabKeyDown}
          class="scope-tab ${!isRouteTab ? "active" : ""}"
        >
          ${store.t("dialogs.sc_tab_entity")}
        </button>
      </div>

      <div
        id="shortcut-tabpanel"
        role="tabpanel"
        aria-labelledby=${isRouteTab ? "shortcut-tab-route" : "shortcut-tab-entity"}
        class="stack"
      >
        ${isRouteTab
          ? html`<div class="stacked-field">
              <label for="shortcut-route-select">
                ${scIsDock
                  ? store.t("dialogs.sc_target_subpage")
                  : store.t("dialogs.sc_target_app_page")}
              </label>
              <select
                id="shortcut-route-select"
                .value=${live(effectiveRouteTarget)}
                @change=${(ev: Event) => {
                  const val = (ev.currentTarget as HTMLSelectElement).value;
                  store.shortcutModal = { ...store.shortcutModal, routeTarget: val };
                  store.host.requestUpdate();
                }}
              >
                ${routeGroups.map(
                  (grp) => html`<optgroup label=${grp.group}>
                    ${grp.items.map(
                      (item) => html`<option
                        value=${item.token}
                        .selected=${live(item.token === effectiveRouteTarget)}
                      >
                        ${item.label}
                      </option>`,
                    )}
                  </optgroup>`,
                )}
              </select>
            </div>`
          : html`<div class="stacked-field">
                <label for="shortcut-domain-filter">
                  ${store.t("dialogs.sc_domain_filter")}
                </label>
                <select
                  id="shortcut-domain-filter"
                  .value=${live(scModal.entityDomainFilter)}
                  @change=${(ev: Event) => {
                    const nextDom = (ev.currentTarget as HTMLSelectElement).value;
                    const nextList = allShortcutEntities.filter(
                      (e) => nextDom === "all" || e.domain === nextDom,
                    );
                    const keepEnt = nextList.some((e) => e.id === scModal.entityTarget)
                      ? scModal.entityTarget
                      : nextList[0]?.id || "";
                    const effDom = keepEnt.split(".", 1)[0] || nextDom;
                    const nextAct = SHORTCUT_DOMAIN_ACTIONS[effDom]?.[0]?.action || "";
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      entityDomainFilter: nextDom,
                      entityTarget: keepEnt,
                      action: nextAct,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  <option value="all" .selected=${live(scModal.entityDomainFilter === "all")}>
                    ${store.t("dialogs.sc_all_domains")}
                  </option>
                  ${availableDomains.map(
                    (dom) => html`<option
                      value=${dom}
                      .selected=${live(dom === scModal.entityDomainFilter)}
                    >
                      ${SHORTCUT_DOMAIN_LABELS[dom] || dom}
                    </option>`,
                  )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="shortcut-entity-select">
                  ${store.t("dialogs.shortcut_entity_label")}
                </label>
                ${renderEntityCombobox({
                  id: "shortcut-entity-select",
                  value: scModal.entityTarget,
                  options: comboboxOptions,
                  ariaLabel: store.t("dialogs.shortcut_entity_label"),
                  placeholder: store.t("combobox.placeholder"),
                  allowClear: false,
                  host: store.host,
                  overlay: store.localeOverlay,
                  onChange: (nextEnt) => {
                    const dom = nextEnt.split(".", 1)[0] || "";
                    const acts = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
                    const nextAct = acts.some((a) => a.action === scModal.action)
                      ? scModal.action
                      : acts[0]?.action || "";
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      entityTarget: nextEnt,
                      action: nextAct,
                    };
                    store.host.requestUpdate();
                  },
                })}
              </div>
              <div class="stacked-field">
                <label for="shortcut-action-select">
                  ${store.t("dialogs.sc_action_label")}
                </label>
                <select
                  id="shortcut-action-select"
                  .value=${live(scModal.action)}
                  @change=${(ev: Event) => {
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      action: (ev.currentTarget as HTMLSelectElement).value,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${availableEntityActions.map(
                    (act) => html`<option
                      value=${act.action}
                      .selected=${live(act.action === scModal.action)}
                    >
                      ${act.label}
                    </option>`,
                  )}
                </select>
              </div>
              ${renderSwitchRow({
                id: "shortcut-confirm-switch",
                label: store.t("dialogs.sc_confirm_label"),
                description: scIsDock
                  ? store.t("dialogs.sc_confirm_dock_desc")
                  : store.t("dialogs.sc_confirm_pinned_desc"),
                checked: scModal.confirm,
                onChange: (checked) => {
                  store.shortcutModal = { ...store.shortcutModal, confirm: checked };
                  store.host.requestUpdate();
                },
              })}`}
      </div>

      <div class="stacked-field">
        <label for="shortcut-label-input">${store.t("dialogs.sc_custom_label")}</label>
        <input
          type="text"
          id="shortcut-label-input"
          maxlength=${String(SHORTCUT_LABEL_MAX)}
          placeholder=${autoDefaultLabel}
          .value=${focusSafe(scModal.label)}
          @input=${(ev: Event) => {
            store.shortcutModal = {
              ...store.shortcutModal,
              label: (ev.currentTarget as HTMLInputElement).value,
            };
          }}
        />
      </div>

      <div class="stacked-field">
        <label for="shortcut-icon-input">${store.t("dialogs.sc_icon_label")}</label>
        <div class="shortcut-icon-row">
          <span id="shortcut-icon-preview" class=${previewBadgeClass} aria-hidden="true">
            <ha-icon .icon=${previewIcon}></ha-icon>
          </span>
          <input
            type="text"
            id="shortcut-icon-input"
            placeholder=${store.t("dialogs.sc_icon_search_placeholder", {
              total: totalIconsText,
            })}
            .value=${focusSafe(scModal.iconSearch)}
            @input=${(ev: Event) => {
              const raw = (ev.currentTarget as HTMLInputElement).value;
              store.shortcutModal = {
                ...store.shortcutModal,
                iconSearch: raw,
              };
              store.host.requestUpdate();
            }}
          />
          ${scModal.icon || scModal.iconSearch
            ? html`<button
                type="button"
                @click=${() => {
                  store.shortcutModal = {
                    ...store.shortcutModal,
                    icon: "",
                    iconSearch: "",
                  };
                  store.host.requestUpdate();
                }}
                class="btn btn-text btn-compact"
              >
                ${store.t("action.default_icon")}
              </button>`
            : nothing}
        </div>
        <div class="shortcut-picker-bar">
          <p class="row-description shortcut-picker-status">
            ${selectedCustomIcon
              ? store.t("dialogs.sc_icon_selected", { icon: selectedCustomIcon })
              : store.t("dialogs.sc_icon_default", { icon: autoDefaultIcon })}
            •
            ${hasIconQuery
              ? mdiMatchCount === 0
                ? store.t("dialogs.sc_icon_no_matches")
                : mdiMatchCount > filteredMdiIcons.length
                  ? store.t("dialogs.sc_icon_showing_subset", {
                      shown: fmtNumber(filteredMdiIcons.length, store.hass, 0),
                      total: fmtNumber(mdiMatchCount, store.hass, 0),
                    })
                  : mdiMatchCount === 1
                    ? store.t("dialogs.sc_icon_matches_one")
                    : store.t("dialogs.sc_icon_matches_many", {
                        count: fmtNumber(mdiMatchCount, store.hass, 0),
                      })
              : scModal.iconStyleFilter === "all"
                ? store.t("dialogs.sc_icon_popular", { total: totalIconsText })
                : store.t("dialogs.sc_icon_popular_filtered", {
                    style:
                      scModal.iconStyleFilter === "solid"
                        ? store.t("dialogs.sc_icon_style_solid").toLowerCase()
                        : store.t("dialogs.sc_icon_style_outline").toLowerCase(),
                    total: fmtNumber(mdiMatchCount, store.hass, 0),
                  })}
          </p>
          <div
            id="shortcut-icon-style-filter"
            role="radiogroup"
            aria-label=${store.t("dialogs.sc_icon_style_aria")}
            class="segmented shortcut-style-filter"
          >
            ${ICON_STYLE_OPTIONS.map((opt) => {
              const checked = scModal.iconStyleFilter === opt.value;
              return html`<button
                type="button"
                id=${`shortcut-icon-style-${opt.value}`}
                role="radio"
                aria-checked=${checked ? "true" : "false"}
                tabindex=${checked ? "0" : "-1"}
                @click=${() => setIconStyleFilter(opt.value)}
                @keydown=${(ev: KeyboardEvent) =>
                  handleRadioGroupKeyDown(
                    ev,
                    iconStyleValues,
                    scModal.iconStyleFilter,
                    setIconStyleFilter,
                    "shortcut-icon-style-",
                  )}
              >
                ${store.t(opt.labelKey)}
              </button>`;
            })}
          </div>
        </div>
        <div
          role="group"
          aria-label=${store.t("dialogs.sc_mdi_group_aria")}
          class="mdi-picker-grid"
        >
          ${filteredMdiIcons.map((slug) => {
            const isSelected = selectedCustomIcon === slug;
            return html`<button
              type="button"
              title=${slug}
              aria-label=${humanizeMdiIconLabel(slug)}
              aria-pressed=${isSelected ? "true" : "false"}
              @click=${() => {
                store.shortcutModal = {
                  ...store.shortcutModal,
                  icon: slug,
                };
                store.host.requestUpdate();
              }}
              class="mdi-picker-btn ${isSelected ? "selected" : ""}"
            >
              <ha-icon .icon=${slug}></ha-icon>
            </button>`;
          })}
        </div>
      </div>

      <div class="stacked-field">
        <span id="shortcut-badge-style-label" class="field-label">
          ${store.t("dialogs.sc_badge_style_label")}
        </span>
        <div
          id="shortcut-badge-style-group"
          role="radiogroup"
          aria-labelledby="shortcut-badge-style-label"
          class="segmented shortcut-badge-style"
        >
          ${SHORTCUT_BADGE_STYLES_CATALOG.map((item) => {
            const checked = activeBadgeStyleToken === item.token;
            const lblKey = BADGE_STYLE_LABEL_KEYS[item.token];
            return html`<button
              type="button"
              id=${`shortcut-badge-style-${item.token}`}
              role="radio"
              aria-checked=${checked ? "true" : "false"}
              tabindex=${checked ? "0" : "-1"}
              @click=${() => setBadgeStyleToken(item.token)}
              @keydown=${(ev: KeyboardEvent) =>
                handleRadioGroupKeyDown(
                  ev,
                  badgeStyleTokens,
                  activeBadgeStyleToken,
                  setBadgeStyleToken,
                  "shortcut-badge-style-",
                )}
            >
              ${lblKey ? store.t(lblKey) : item.label}
            </button>`;
          })}
        </div>
      </div>

      <div class="stacked-field">
        <span id="shortcut-accent-label" class="field-label">
          ${store.t("dialogs.sc_accent_label")}
        </span>
        <div
          id="shortcut-accent-group"
          role="radiogroup"
          aria-labelledby="shortcut-accent-label"
          class="shortcut-accent-pills"
        >
          ${SHORTCUT_ACCENTS_CATALOG.map((item) => {
            const checked = activeAccentToken === item.token;
            const lblKey = ACCENT_LABEL_KEYS[item.token];
            return html`<button
              type="button"
              id=${`shortcut-accent-${item.token}`}
              role="radio"
              aria-checked=${checked ? "true" : "false"}
              tabindex=${checked ? "0" : "-1"}
              @click=${() => setAccentToken(item.token)}
              @keydown=${(ev: KeyboardEvent) =>
                handleRadioGroupKeyDown(
                  ev,
                  accentTokens,
                  activeAccentToken,
                  setAccentToken,
                  "shortcut-accent-",
                )}
              class="accent-pill-btn"
            >
              <span
                class=${`accent-swatch-dot swatch-${item.token}`}
                aria-hidden="true"
              ></span>
              <span>${lblKey ? store.t(lblKey) : item.label}</span>
            </button>`;
          })}
        </div>
      </div>

      ${!scIsDock
        ? (() => {
            const dims = resolveDeviceGridDims(devCaps);
            const pinnedItems = store.entity.getPinnedItems();
            const pageTitles = store.entity.getPinnedPageTitles();
            const resolved = resolveTileGridLayout(pinnedItems, dims.cols, dims.rows);
            const titleKeys = Object.keys(pageTitles);
            const maxTitlePage = titleKeys.reduce((m, k) => Math.max(m, Number(k) || 0), 0);
            const basePages = Math.max(
              1,
              resolved.pageCount,
              titleKeys.length > 0 ? maxTitlePage + 1 : 1,
            );
            const totalPages = Math.min(
              MAX_PINNED_GRID_PAGES,
              Math.max(
                basePages + Math.max(0, store.pinnedExtraPages),
                scModal.tilePage + 1,
              ),
            );
            const selectedCs = Math.max(1, Math.min(dims.cols, scModal.tileColSpan || 1));
            const selectedRs = Math.max(1, Math.min(dims.rows, scModal.tileRowSpan || 1));
            const hoverSpan = hoveredSpanByStore.get(store) ?? null;
            const previewW = hoverSpan ? hoverSpan.w : selectedCs;
            const previewH = hoverSpan ? hoverSpan.h : selectedRs;
            const excludeIdx = scModal.editIndex !== null ? scModal.editIndex : -1;

            const spanFitsWithoutReflow = (w: number, h: number): boolean => {
              if (scModal.tileCol === null || scModal.tileRow === null) return true;
              if (
                canPlaceTile(
                  resolved,
                  excludeIdx,
                  scModal.tilePage,
                  scModal.tileCol,
                  scModal.tileRow,
                  w,
                  h,
                  dims.cols,
                  dims.rows,
                )
              ) {
                return true;
              }
              const shiftedCol = Math.min(scModal.tileCol, dims.cols - w);
              const shiftedRow = Math.min(scModal.tileRow, dims.rows - h);
              return canPlaceTile(
                resolved,
                excludeIdx,
                scModal.tilePage,
                shiftedCol,
                shiftedRow,
                w,
                h,
                dims.cols,
                dims.rows,
              );
            };

            const selectedWouldReflow = !spanFitsWithoutReflow(selectedCs, selectedRs);
            const matrixCells: Array<{ w: number; h: number }> = [];
            for (let h = 1; h <= dims.rows; h += 1) {
              for (let w = 1; w <= dims.cols; w += 1) {
                matrixCells.push({ w, h });
              }
            }
            const pageOptions = Array.from({ length: totalPages }, (_, idx) => idx);

            return html`<div class="shortcut-tile-layout">
              <span class="field-label">${store.t("dialogs.sc_tile_layout_label")}</span>
              <div class="shortcut-tile-layout-row">
                <div class="stacked-field shortcut-span-field">
                  <div class="shortcut-span-header">
                    <span id="shortcut-tile-size-label" class="field-label">
                      ${store.t("dialogs.sc_tile_size_label")}
                    </span>
                    <span id="shortcut-tile-size-badge" class="chip">
                      ${store.t("dialogs.sc_tile_size_badge", {
                        cols: previewW,
                        rows: previewH,
                      })}
                    </span>
                  </div>
                  <div
                    id="shortcut-span-matrix"
                    role="group"
                    aria-label=${store.t("dialogs.sc_tile_size_aria", {
                      cols: dims.cols,
                      rows: dims.rows,
                    })}
                    style="--grid-cols: ${dims.cols}; --grid-rows: ${dims.rows};"
                    @mouseleave=${() => {
                      if (hoveredSpanByStore.has(store)) {
                        hoveredSpanByStore.delete(store);
                        store.host.requestUpdate();
                      }
                    }}
                    class="span-matrix"
                  >
                    ${matrixCells.map(({ w, h }) => {
                      const inSelected = w <= selectedCs && h <= selectedRs;
                      const inHover = hoverSpan !== null && w <= hoverSpan.w && h <= hoverSpan.h;
                      const isCurrent = w === selectedCs && h === selectedRs;
                      const wouldReflow = !spanFitsWithoutReflow(w, h);
                      return html`<button
                        type="button"
                        data-span-w=${String(w)}
                        data-span-h=${String(h)}
                        aria-label=${store.t("dialogs.sc_tile_size_cell_aria", {
                          cols: w,
                          rows: h,
                        })}
                        aria-pressed=${isCurrent ? "true" : "false"}
                        @mouseenter=${() => {
                          hoveredSpanByStore.set(store, { w, h });
                          store.host.requestUpdate();
                        }}
                        @click=${() => {
                          store.shortcutModal = {
                            ...store.shortcutModal,
                            tileColSpan: w,
                            tileRowSpan: h,
                          };
                          store.host.requestUpdate();
                        }}
                        class="span-matrix-cell${inSelected ? " selected" : ""}${inHover ? " hovered" : ""}${wouldReflow ? " would-reflow" : ""}"
                      ></button>`;
                    })}
                  </div>
                  ${selectedWouldReflow
                    ? html`<p class="row-description">
                        ${store.t("dialogs.sc_span_reflow_hint")}
                      </p>`
                    : nothing}
                </div>

                <div class="stacked-field shortcut-page-field">
                  <label for="shortcut-page-select">${store.t("dialogs.sc_page_label")}</label>
                  <select
                    id="shortcut-page-select"
                    .value=${live(String(scModal.tilePage))}
                    @change=${(ev: Event) => {
                      const raw = (ev.currentTarget as HTMLSelectElement).value;
                      if (raw === "__new__") {
                        const newIdx = totalPages;
                        store.pinnedExtraPages = Math.max(
                          store.pinnedExtraPages,
                          newIdx - basePages + 1,
                        );
                        store.shortcutModal = {
                          ...store.shortcutModal,
                          tilePage: newIdx,
                          tileCol: null,
                          tileRow: null,
                        };
                      } else {
                        const nextPage = Math.max(0, Math.min(totalPages - 1, Number(raw) || 0));
                        const movedPage = nextPage !== scModal.tilePage;
                        store.shortcutModal = {
                          ...store.shortcutModal,
                          tilePage: nextPage,
                          tileCol: movedPage ? null : scModal.tileCol,
                          tileRow: movedPage ? null : scModal.tileRow,
                        };
                      }
                      store.host.requestUpdate();
                    }}
                  >
                    ${pageOptions.map((pIdx) => {
                      const customTitle = pageTitles[String(pIdx)];
                      const optLabel = customTitle
                        ? store.t("dialogs.sc_page_titled_option", {
                            page: pIdx + 1,
                            title: customTitle,
                          })
                        : store.t("dialogs.pinned_page_slot", { page: pIdx + 1 });
                      return html`<option
                        value=${String(pIdx)}
                        .selected=${live(pIdx === scModal.tilePage)}
                      >
                        ${optLabel}
                      </option>`;
                    })}
                    ${totalPages < MAX_PINNED_GRID_PAGES
                      ? html`<option value="__new__" .selected=${live(false)}>
                          ${store.t("dialogs.sc_page_new_option")}
                        </option>`
                      : nothing}
                  </select>
                </div>
              </div>
            </div>`;
          })()
        : nothing}

      <div class="dialog-actions">
        <button type="button" @click=${close} class="btn btn-secondary">
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          id="shortcut-save-btn"
          @click=${() => store.entity.saveShortcutModal()}
          class="btn btn-primary"
        >
          ${store.t("action.save_shortcut")}
        </button>
      </div>
    </div>
  </dialog>`;
}
