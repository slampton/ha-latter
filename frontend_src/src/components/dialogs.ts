/**
 * Native `<dialog>` Modals for Latter Studio (Remove Device, Reset Device, Add BLE Tag, Custom Color Wheel).
 * Uses component-scoped pointer capture on `<canvas>` — zero `window.*` listeners.
 */

import { SHORTCUT_LABEL_MAX, SHORTCUT_ROUTES_CATALOG } from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import {
  isKnownMdiIcon,
  MDI_TOTAL_ICON_COUNT,
  normalizeMdiIconSlug,
  ROUTE_PREVIEW_ICONS,
  searchMdiIcons,
  SHORTCUT_DOMAIN_ACTIONS,
  SHORTCUT_DOMAIN_LABELS,
} from "../mdi-catalog.js";
import type { StudioStore } from "../state/store.js";
import { hsvToHex, hsvToRgbJS, isValidHexColor } from "../utils/format.js";
import { renderSelectOptions, renderSwitchRow } from "./controls.js";

let cwWheelPainted = false;

function paintHsvColorWheel(canvas: HTMLCanvasElement): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const size = canvas.width;
  const radius = size / 2;
  const img = ctx.createImageData(size, size);
  const data = img.data;
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = x - radius;
      const dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * size + x) * 4;
      if (dist > radius) {
        data[idx + 3] = 0;
        continue;
      }
      const sat = Math.min(1, dist / radius);
      const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
      const [r, g, b] = hsvToRgbJS(angle, sat, 1);
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function pickWheelHexFromEvent(canvas: HTMLCanvasElement, ev: PointerEvent): string | null {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = ev.clientX - rect.left - cx;
  const dy = ev.clientY - rect.top - cy;
  const radius = Math.min(cx, cy);
  const sat = Math.min(1, Math.sqrt(dx * dx + dy * dy) / radius);
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  return hsvToHex(angle, sat, 1);
}

export function syncStudioDialogs(renderRoot: ShadowRoot, store: StudioStore): void {
  const pairs: Array<[string, boolean]> = [
    ["latter-rm-modal", store.removeModal.open],
    ["latter-reset-modal", store.resetModal.open],
    ["latter-add-dev-modal", store.addBleModal.open],
    ["latter-cw-modal", store.colorWheelModal.open],
    ["latter-save-group-modal", store.saveGroupModal?.open ?? false],
    ["latter-shortcut-modal", store.shortcutModal?.open ?? false],
  ];
  for (const [id, wantOpen] of pairs) {
    const dlg = renderRoot.getElementById(id) as HTMLDialogElement | null;
    if (!dlg) continue;
    if (wantOpen && !dlg.open) {
      try {
        dlg.showModal();
      } catch {
        dlg.setAttribute("open", "");
      }
    } else if (!wantOpen && dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
  }
  if (store.colorWheelModal.open && !cwWheelPainted) {
    const canvas = renderRoot.getElementById("latter-cw-canvas") as HTMLCanvasElement | null;
    if (canvas) {
      paintHsvColorWheel(canvas);
      cwWheelPainted = true;
    }
  } else if (!store.colorWheelModal.open) {
    cwWheelPainted = false;
  }
}

export function renderStudioDialogs(store: StudioStore): TemplateResult {
  const persons = store.state?.catalog?.persons || [];
  const candidates = store.state?.discovered_ble_devices || [];

  const onBackdropClick = (ev: Event, closeFn: () => void): void => {
    if (ev.target === ev.currentTarget) {
      closeFn();
    }
  };

  const onCwPointerDown = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    canvas.setPointerCapture?.(pev.pointerId);
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerMove = (ev: Event): void => {
    const pev = ev as PointerEvent;
    if (pev.buttons === 0) return;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerUp = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    if (canvas.hasPointerCapture?.(pev.pointerId)) {
      canvas.releasePointerCapture(pev.pointerId);
    }
  };

  const onCwHexInput = (ev: Event): void => {
    const raw = (ev.currentTarget as HTMLInputElement).value;
    store.colorWheelModal = { ...store.colorWheelModal, hex: raw.toUpperCase() };
    store.host.requestUpdate();
  };

  const onCwNameInput = (ev: Event): void => {
    store.colorWheelModal = {
      ...store.colorWheelModal,
      name: (ev.currentTarget as HTMLInputElement).value,
    };
  };

  const cwValidHex = isValidHexColor(store.colorWheelModal.hex)
    ? store.colorWheelModal.hex
    : "";

  const scModal = store.shortcutModal;
  const scIsDock = scModal.listKey === "dock_items";
  const scTitle =
    scModal.editIndex !== null
      ? scIsDock
        ? "Edit Dock Shortcut"
        : "Edit Pinned Shortcut"
      : scIsDock
        ? "Add Dock Shortcut"
        : "Add Pinned Shortcut";
  const devCaps = store.state?.capabilities || {};
  const availableRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!scIsDock && r.dockOnly) return false;
    if (scIsDock && r.token === "settings:root") return false;
    if (r.capability === "round" && devCaps.is_round === false) return false;
    if (r.capability === "imu" && devCaps.has_imu === false) return false;
    return true;
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
  const scSearchLower = scModal.entitySearch.trim().toLowerCase();
  const filteredShortcutEntities = allShortcutEntities.filter((e) => {
    if (scModal.entityDomainFilter !== "all" && e.domain !== scModal.entityDomainFilter) {
      return false;
    }
    if (!scSearchLower) return true;
    return (
      e.name.toLowerCase().includes(scSearchLower) ||
      e.id.toLowerCase().includes(scSearchLower) ||
      e.area_name.toLowerCase().includes(scSearchLower)
    );
  });
  const selectedEntityObj =
    allShortcutEntities.find((e) => e.id === scModal.entityTarget) || null;
  const selectedEntityDomain = selectedEntityObj
    ? selectedEntityObj.domain
    : (scModal.entityTarget.split(".", 1)[0] || "");
  const availableEntityActions = SHORTCUT_DOMAIN_ACTIONS[selectedEntityDomain] || [];
  const selectedRouteSpec =
    availableRoutes.find((r) => r.token === scModal.routeTarget) ||
    SHORTCUT_ROUTES_CATALOG.find((r) => r.token === scModal.routeTarget);
  const autoDefaultLabel =
    scModal.kind === "route"
      ? selectedRouteSpec?.label || "Shortcut"
      : selectedEntityObj?.name || scModal.entityTarget || "Entity Action";
  const autoDefaultIcon =
    scModal.kind === "route"
      ? ROUTE_PREVIEW_ICONS[scModal.routeTarget] || "mdi:apps"
      : selectedEntityObj?.icon || "mdi:flash";
  const selectedCustomIcon = normalizeMdiIconSlug(scModal.icon);
  const typedSearchIcon = normalizeMdiIconSlug(scModal.iconSearch);
  const previewIcon =
    selectedCustomIcon ||
    (isKnownMdiIcon(typedSearchIcon) ? typedSearchIcon : autoDefaultIcon);
  const hasIconQuery = scModal.iconSearch.trim().length > 0;
  const { items: filteredMdiIcons, totalMatches: mdiMatchCount } = searchMdiIcons(
    scModal.iconSearch,
    120,
  );

  return html`
    <dialog
      id="latter-rm-modal"
      aria-labelledby="latter-rm-title"
      @cancel=${() => store.closeRemoveDeviceModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeRemoveDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-rm-title" class="dialog-title">Remove Device From Latter?</h3>
        <p class="dialog-text">
          Removes "${store.removeModal.title || "Device"}" from Latter. Your ESPHome device stays in Home Assistant.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeRemoveDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.removeModal.busy}
            @click=${() => void store.confirmRemoveDevice()}
            class="btn btn-danger-filled"
          >
            Remove Device
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-reset-modal"
      aria-labelledby="latter-reset-title"
      @cancel=${() => store.closeResetDeviceModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeResetDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-reset-title" class="dialog-title">Reset to Defaults?</h3>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "latter-reset-device-settings",
            label: "Settings Saved on the Device",
            description: "Erases everything saved on the Device; it restarts.",
            checked: store.resetModal.deviceSettings,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, deviceSettings: checked };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "latter-reset-latter-options",
            label: "Latter Settings for This Device",
            checked: store.resetModal.latterOptions,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, latterOptions: checked };
              store.host.requestUpdate();
            },
          })}
        </div>
        <p class="dialog-text">
          Wi-Fi and pairing are kept, so the Device rejoins Home Assistant by itself. Its ESPHome binding and Music Assistant player link are kept too.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeResetDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-reset-confirm-btn"
            ?disabled=${store.resetModal.busy || (!store.resetModal.deviceSettings && !store.resetModal.latterOptions)}
            @click=${() => void store.confirmResetDevice()}
            class="btn btn-danger-filled"
          >
            Reset
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-add-dev-modal"
      aria-labelledby="latter-add-dev-title"
      @cancel=${() => store.closeAddBleModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeAddBleModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-add-dev-title" class="dialog-title">Add a BLE Tag</h3>
        <p class="dialog-text">
          A phone, watch or Bluetooth tag that Latter tracks by Area. Latter Devices are added in Home Assistant.
        </p>
        <div class="stacked-field">
          <label for="ble-candidate-picker">Discovered Bluetooth Devices</label>
          <select
            id="ble-candidate-picker"
            .value=${store.addBleModal.candidateAddr}
            @change=${(ev: Event) =>
              store.selectBleCandidateInModal((ev.currentTarget as HTMLSelectElement).value)}
          >
            <option value="">Enter manually…</option>
            ${candidates.map((c) => {
              const addr = c.target_address || c.address || "";
              const lbl =
                c.label ||
                `${c.title || c.name || addr}${c.area_name ? ` (${c.area_name})` : ""}`;
              return html`<option value=${addr} ?selected=${addr === store.addBleModal.candidateAddr}>
                ${lbl}
              </option>`;
            })}
          </select>
        </div>
        <div class="stacked-field">
          <label for="ble-custom-name">Name</label>
          <input
            type="text"
            id="ble-custom-name"
            placeholder="e.g. phone, watch, keys"
            .value=${store.addBleModal.name}
            @input=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                name: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <span class="field-label">Target Address or Entity</span>
          <input
            type="text"
            id="ble-custom-addr"
            placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
            .value=${store.addBleModal.address}
            @input=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                address: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
            class="mono"
          />
        </div>
        <div class="stacked-field">
          <label for="ble-custom-person">Assigned Person (Optional)</label>
          <select
            id="ble-custom-person"
            .value=${store.addBleModal.assignedPerson}
            @change=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                assignedPerson: (ev.currentTarget as HTMLSelectElement).value,
              };
            }}
          >
            ${renderSelectOptions(persons, store.addBleModal.assignedPerson, "Unassigned")}
          </select>
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeAddBleModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.addBleModal.busy}
            @click=${() => void store.confirmAddBleModal()}
            class="btn btn-primary"
          >
            Add BLE Tag
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-cw-modal"
      aria-labelledby="latter-cw-title"
      @cancel=${() => store.closeColorWheelModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeColorWheelModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-cw-title" class="dialog-title">Add a Custom Color</h3>
        <div class="color-wheel" aria-hidden="true">
          <canvas
            id="latter-cw-canvas"
            width="220"
            height="220"
            @pointerdown=${onCwPointerDown}
            @pointermove=${onCwPointerMove}
            @pointerup=${onCwPointerUp}
          ></canvas>
        </div>
        <div class="color-hex-row">
          <input
            type="color"
            id="latter-cw-native"
            aria-label="Color"
            .value=${cwValidHex}
            @input=${onCwHexInput}
          />
          <input
            type="text"
            id="latter-cw-hex"
            aria-label="Hex color"
            placeholder="#RRGGBB"
            maxlength="7"
            .value=${store.colorWheelModal.hex}
            @input=${onCwHexInput}
          />
        </div>
        <div class="stacked-field">
          <label for="latter-cw-name">Name</label>
          <input
            type="text"
            id="latter-cw-name"
            placeholder="e.g. Sunset Coral"
            .value=${store.colorWheelModal.name}
            @input=${onCwNameInput}
          />
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeColorWheelModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            @click=${() => void store.saveColorWheelSelection()}
            class="btn btn-primary"
          >
            Save Color
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-save-group-modal"
      aria-labelledby="latter-save-group-title"
      @cancel=${() => store.closeSaveGroupModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeSaveGroupModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-save-group-title" class="dialog-title">Save Custom Group</h3>
        <p class="dialog-text">
          Saves this Device's settings as a reusable Device Group and assigns this Device to it.
        </p>
        <div class="stacked-field">
          <label for="save-group-name">Group Name</label>
          <input
            type="text"
            id="save-group-name"
            placeholder="e.g. Nightstands, Guest Suites"
            .value=${store.saveGroupModal?.name || ""}
            @input=${(ev: Event) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                name: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <label for="save-group-desc">Description (Optional)</label>
          <input
            type="text"
            id="save-group-desc"
            placeholder="Optional summary of these settings"
            .value=${store.saveGroupModal?.description || ""}
            @input=${(ev: Event) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                description: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "save-group-include-display",
            label: "Include Display Settings",
            description: "Sync wallpapers, clock face, color profile, and media styling.",
            checked: Boolean(store.saveGroupModal?.includeDisplay),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeDisplay: checked,
              };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "save-group-include-interface",
            label: "Include Interface & Shortcuts",
            description: "Sync start screen, App Dock, pinned shortcuts, and hub categories.",
            checked: Boolean(store.saveGroupModal?.includeInterface),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeInterface: checked,
              };
              store.host.requestUpdate();
            },
          })}
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeSaveGroupModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-save-group-confirm-btn"
            ?disabled=${Boolean(store.saveGroupModal?.busy)}
            @click=${() => void store.confirmSaveGroupModal()}
            class="btn btn-primary"
          >
            Save Group
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-shortcut-modal"
      aria-labelledby="latter-shortcut-title"
      @cancel=${() => store.closeShortcutModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeShortcutModal())}
      class="studio-dialog shortcut-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-shortcut-title" class="dialog-title">${scTitle}</h3>
        <div class="scope-tabs" role="tablist" aria-label="Shortcut Type">
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "route")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "route" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "route" ? "active" : ""}"
          >
            App or Page
          </button>
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "entity")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "entity" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "entity" ? "active" : ""}"
          >
            Home Assistant Entity
          </button>
        </div>

        ${scModal.kind === "route"
          ? html`<div class="stacked-field">
              <label for="shortcut-route-select">Target App or Subpage</label>
              <select
                id="shortcut-route-select"
                .value=${scModal.routeTarget}
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
                        ?selected=${item.token === scModal.routeTarget}
                      >
                        ${item.label}
                      </option>`,
                    )}
                  </optgroup>`,
                )}
              </select>
            </div>`
          : html`<div class="list-row-main">
                <div class="stacked-field">
                  <label for="shortcut-domain-filter">Domain Filter</label>
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
                        : (nextList[0]?.id || "");
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
                      All Domains
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
                  <label for="shortcut-entity-search">Filter Entities</label>
                  <input
                    type="search"
                    id="shortcut-entity-search"
                    placeholder="Search name, Area, or entity ID…"
                    .value=${scModal.entitySearch}
                    @input=${(ev: Event) => {
                      const query = (ev.currentTarget as HTMLInputElement).value;
                      const qLow = query.trim().toLowerCase();
                      const matches = allShortcutEntities.filter((e) => {
                        if (
                          scModal.entityDomainFilter !== "all" &&
                          e.domain !== scModal.entityDomainFilter
                        ) {
                          return false;
                        }
                        if (!qLow) return true;
                        return (
                          e.name.toLowerCase().includes(qLow) ||
                          e.id.toLowerCase().includes(qLow) ||
                          e.area_name.toLowerCase().includes(qLow)
                        );
                      });
                      const nextTarget = matches.some((e) => e.id === scModal.entityTarget)
                        ? scModal.entityTarget
                        : (matches[0]?.id || scModal.entityTarget);
                      const nextDom = nextTarget.split(".", 1)[0] || "";
                      const validActs = SHORTCUT_DOMAIN_ACTIONS[nextDom] || [];
                      const nextAct = validActs.some((a) => a.action === scModal.action)
                        ? scModal.action
                        : (validActs[0]?.action || scModal.action);
                      store.shortcutModal = {
                        ...store.shortcutModal,
                        entitySearch: query,
                        entityTarget: nextTarget,
                        action: nextAct,
                      };
                      store.host.requestUpdate();
                    }}
                  />
                </div>
              </div>
              <div class="stacked-field">
                <label for="shortcut-entity-select">Entity</label>
                <select
                  id="shortcut-entity-select"
                  .value=${scModal.entityTarget}
                  @change=${(ev: Event) => {
                    const nextEnt = (ev.currentTarget as HTMLSelectElement).value;
                    const dom = nextEnt.split(".", 1)[0] || "";
                    const acts = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
                    const nextAct = acts.some((a) => a.action === scModal.action)
                      ? scModal.action
                      : (acts[0]?.action || "");
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      entityTarget: nextEnt,
                      action: nextAct,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${filteredShortcutEntities.length === 0
                    ? html`<option value="">No matching Home Assistant entities</option>`
                    : filteredShortcutEntities.map(
                        (e) => html`<option
                          value=${e.id}
                          ?selected=${e.id === scModal.entityTarget}
                        >
                          ${e.area_name ? `${e.area_name} — ` : ""}${e.name} (${e.id})
                        </option>`,
                      )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="shortcut-action-select">Action</label>
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
                label: "Confirm Before Running",
                description: scIsDock
                  ? "Shows a confirmation prompt before running this action from the App Dock."
                  : "Require a confirmation tap instead of running immediately on a single tap.",
                checked: scModal.confirm,
                onChange: (checked) => {
                  store.shortcutModal = { ...store.shortcutModal, confirm: checked };
                  store.host.requestUpdate();
                },
              })}`}

        <div class="stacked-field">
          <label for="shortcut-label-input">Custom Label (Optional)</label>
          <input
            type="text"
            id="shortcut-label-input"
            maxlength=${String(SHORTCUT_LABEL_MAX)}
            placeholder=${autoDefaultLabel}
            .value=${scModal.label}
            @input=${(ev: Event) => {
              store.shortcutModal = {
                ...store.shortcutModal,
                label: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>

        <div class="stacked-field">
          <label for="shortcut-icon-input">Icon (Optional MDI Override)</label>
          <div class="shortcut-icon-row">
            <span class="shortcut-icon-badge" aria-hidden="true">
              <ha-icon .icon=${previewIcon}></ha-icon>
            </span>
            <input
              type="text"
              id="shortcut-icon-input"
              placeholder=${`Search all ${MDI_TOTAL_ICON_COUNT.toLocaleString()} icons (e.g. teddy-bear, baby, lamp)…`}
              .value=${scModal.iconSearch}
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
                  Default Icon
                </button>`
              : nothing}
          </div>
          <p class="row-description">
            ${selectedCustomIcon
              ? `Selected: ${selectedCustomIcon}`
              : `Default: ${autoDefaultIcon}`}
            •
            ${hasIconQuery
              ? mdiMatchCount === 0
                ? "No matching icons — try another keyword"
                : mdiMatchCount > filteredMdiIcons.length
                  ? `Showing ${filteredMdiIcons.length} of ${mdiMatchCount.toLocaleString()} matches`
                  : `${mdiMatchCount.toLocaleString()} matching icon${mdiMatchCount === 1 ? "" : "s"}`
              : `Showing popular icons (${MDI_TOTAL_ICON_COUNT.toLocaleString()} searchable)`}
          </p>
          <div class="mdi-picker-grid" role="listbox" aria-label="Material Design Icons">
            ${filteredMdiIcons.map(
              (slug) => html`<button
                type="button"
                title=${slug}
                aria-label=${slug}
                aria-selected=${String(selectedCustomIcon === slug)}
                @click=${() => {
                  store.shortcutModal = {
                    ...store.shortcutModal,
                    icon: slug,
                  };
                  store.host.requestUpdate();
                }}
                class="mdi-picker-btn ${selectedCustomIcon === slug ? "selected" : ""}"
              >
                <ha-icon .icon=${slug}></ha-icon>
              </button>`,
            )}
          </div>
        </div>

        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeShortcutModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="shortcut-save-btn"
            @click=${() => store.saveShortcutModal()}
            class="btn btn-primary"
          >
            Save Shortcut
          </button>
        </div>
      </div>
    </dialog>
  `;
}
