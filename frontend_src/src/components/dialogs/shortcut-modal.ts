/**
 * Add / Edit Shortcut Modal (`#latter-shortcut-modal`, `D-047`, `D-062`, `Q11`).
 * - Short-circuits closed `<dialog>` body (`F-06`, `B-18`, `R-5`)
 * - Roving-arrow `tablist` + `tabpanel` for Shortcut type (`D-07`)
 * - WAI-ARIA `renderEntityCombobox` replacing 1,000+-option `<select>` (`Q11`, `D-18`)
 * - Accessible MDI icon picker (`role="group"` of `aria-pressed` buttons + humanized labels + cached `searchMdiIcons`, `D-08`, `F-07`)
 * - `focusSafe` text inputs
 */

import {
  NATIVE_DOCK_APP_TOKENS,
  SHORTCUT_LABEL_MAX,
  SHORTCUT_ROUTES_CATALOG,
} from "../../constants.js";
import { formatHaEntityState } from "../../i18n/index.js";
import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import {
  isKnownMdiIcon,
  isMdiCatalogLoaded,
  MDI_TOTAL_ICON_COUNT,
  normalizeMdiIconSlug,
  ROUTE_PREVIEW_ICONS,
  searchMdiIcons,
  SHORTCUT_DOMAIN_ACTIONS,
  SHORTCUT_DOMAIN_LABELS,
} from "../../mdi-catalog.js";
import { isCatalogItemSupported, type StudioStore } from "../../state/store.js";
import { fmtNumber } from "../../utils/format.js";
import {
  type ComboboxOptionItem,
  renderEntityCombobox,
  renderSwitchRow,
} from "../controls.js";

interface CachedMdiSearch {
  queryKey: string;
  loaded: boolean;
  items: readonly string[];
  totalMatches: number;
}

let mdiSearchCache: CachedMdiSearch | null = null;

function getCachedMdiSearch(rawQuery: string): { items: readonly string[]; totalMatches: number } {
  const queryKey = String(rawQuery || "").trim().toLowerCase();
  const loaded = isMdiCatalogLoaded();
  if (
    mdiSearchCache &&
    mdiSearchCache.queryKey === queryKey &&
    mdiSearchCache.loaded === loaded
  ) {
    return { items: mdiSearchCache.items, totalMatches: mdiSearchCache.totalMatches };
  }
  const result = searchMdiIcons(rawQuery, 120);
  mdiSearchCache = {
    queryKey,
    loaded,
    items: result.items,
    totalMatches: result.totalMatches,
  };
  return result;
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
  );
  const totalIconsText = fmtNumber(MDI_TOTAL_ICON_COUNT, store.hass, 0);

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
                .value=${effectiveRouteTarget}
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
                        ?selected=${item.token === effectiveRouteTarget}
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
                  .value=${scModal.entityDomainFilter}
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
                  <option value="all" ?selected=${scModal.entityDomainFilter === "all"}>
                    ${store.t("dialogs.sc_all_domains")}
                  </option>
                  ${availableDomains.map(
                    (dom) => html`<option
                      value=${dom}
                      ?selected=${dom === scModal.entityDomainFilter}
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
                  .value=${scModal.action}
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
                      ?selected=${act.action === scModal.action}
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
          <span class="shortcut-icon-badge" aria-hidden="true">
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
        <p class="row-description">
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
            : store.t("dialogs.sc_icon_popular", { total: totalIconsText })}
        </p>
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
