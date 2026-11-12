/**
 * `<latter-studio>` Custom Element — Modular TypeScript + Lit Architecture (`D-023`).
 *
 * - Zero global `window` property bindings; state is owned per element by `StudioStore`.
 * - Active-view-only rendering via `renderActiveView(this.store)`.
 * - Full WAI-ARIA `tablist` / roving arrow-key focus on Scope tabs and `aria-current="page"` on sidebar nav.
 * - Dedicated reload banner when `studio_rev_mismatch` is signaled after an HACS update.
 */

import { renderStudioDialogs, syncStudioDialogs } from "./components/dialogs.js";
import { html, LitElement, nothing, type TemplateResult } from "./lib/lit.js";
import { StudioStore } from "./state/store.js";
import { STUDIO_STYLES } from "./styles/tokens.js";
import type { DeviceViewId, HassRoute, HomeAssistant, SystemViewId } from "./types.js";
import { renderActiveView } from "./views/index.js";

const SYSTEM_NAV_ITEMS: ReadonlyArray<{ viewId: SystemViewId; label: string }> = [
  { viewId: "system_overview", label: "Overview" },
  { viewId: "shared_entities", label: "Shared Entities" },
  { viewId: "remotes", label: "Media & Remotes" },
  { viewId: "system_sync", label: "Device Groups" },
  { viewId: "area_tracking", label: "BLE & Area Presence" },
  { viewId: "system_tools", label: "Tools" },
];

export class LatterStudio extends LitElement {
  static override styles = STUDIO_STYLES;

  readonly store: StudioStore;

  private _narrow = false;
  private _route: HassRoute | null = null;
  private _panel: Record<string, unknown> | null = null;
  private _routeInitialized = false;

  constructor() {
    super();
    this.store = new StudioStore(this);
    this.addController(this.store);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (!this._routeInitialized) {
      this._routeInitialized = true;
      this._applyRoute();
    }
  }

  set hass(h: HomeAssistant | null) {
    this.toggleAttribute("dark", Boolean(h?.themes?.darkMode ?? h?.selectedTheme?.dark));
    this.store.setHass(h);
  }

  get hass(): HomeAssistant | null {
    return this.store.hass;
  }

  set narrow(n: boolean) {
    const next = Boolean(n);
    if (this._narrow === next) return;
    this._narrow = next;
    this.toggleAttribute("narrow", next);
    this.requestUpdate();
  }

  get narrow(): boolean {
    return this._narrow;
  }

  set panel(p: Record<string, unknown> | null) {
    this._panel = p;
  }

  get panel(): Record<string, unknown> | null {
    return this._panel;
  }

  set route(r: HassRoute | null) {
    const prevPath = this._route?.path ?? null;
    this._route = r;
    if (this._routeInitialized && r && r.path !== prevPath) {
      this._applyRoute();
    }
  }

  get route(): HassRoute | null {
    return this._route;
  }

  private _applyRoute(): void {
    this.store.applyRoute(this._route);
  }

  private _onScopeTabKeyDown(ev: KeyboardEvent): void {
    if (
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight" &&
      ev.key !== "Home" &&
      ev.key !== "End"
    ) {
      return;
    }
    ev.preventDefault();
    const currentIsDevice = this.store.currentScope === "device";
    let nextScope: "device" | "system";
    if (ev.key === "Home") {
      nextScope = "device";
    } else if (ev.key === "End") {
      nextScope = "system";
    } else {
      nextScope = currentIsDevice ? "system" : "device";
    }

    if (nextScope === "device") {
      this.store.openDevicesLanding();
      const btn = this.renderRoot.querySelector("#tab-scope-device") as HTMLButtonElement | null;
      btn?.focus();
    } else {
      this.store.setScope("system");
      const btn = this.renderRoot.querySelector("#tab-scope-system") as HTMLButtonElement | null;
      btn?.focus();
    }
  }

  protected override updated(): void {
    syncStudioDialogs(this.renderRoot, this.store);
  }

  private _renderDeviceNav(): TemplateResult {
    const data = this.store.state;
    const caps = data?.capabilities || {};
    const isBleOnly = data?.config?.kind === "ble_tag";

    const items: Array<{ viewId: Exclude<DeviceViewId, "select_device_prompt">; label: string; id?: string }> = [
      { viewId: "dashboard", label: "Overview" },
    ];
    if (!isBleOnly && caps.has_display !== false) {
      items.push({ viewId: "home_display", label: "Display & Home", id: "nav-btn-home_display" });
    }
    if (!isBleOnly && (caps.has_audio !== false || caps.has_voice !== false)) {
      items.push({ viewId: "audio_voice", label: "Audio & Voice", id: "nav-btn-audio_voice" });
    }
    if (!isBleOnly && caps.has_power) {
      items.push({ viewId: "power", label: "Power & Battery", id: "nav-btn-power" });
    }
    items.push({ viewId: "presence", label: "BLE & Area Presence" });
    items.push({ viewId: "tools", label: "Tools" });

    return html`<nav id="nav-scope-device" aria-label="Device pages" class="nav-list">
      <button
        type="button"
        @click=${() => this.store.openDevicesLanding()}
        class="nav-btn nav-back-btn"
      >
        <span>&larr; All Devices</span>
      </button>
      <div id="nav-selected-device-label" class="nav-device-title">
        ${data?.title || "—"}
      </div>
      ${items.map((item) => {
        const active = this.store.currentViewId === item.viewId;
        return html`<button
          type="button"
          id=${item.id || nothing}
          data-view=${item.viewId}
          aria-current=${active ? "page" : nothing}
          @click=${() => this.store.switchView(item.viewId)}
          class="nav-btn ${active ? "active" : ""}"
        >
          <span>${item.label}</span>
        </button>`;
      })}
    </nav>`;
  }

  private _renderSidebar(): TemplateResult {
    const isDeviceScope = this.store.currentScope === "device";
    const deviceCount = (this.store.state?.system_devices || []).length;
    const allDevicesActive = isDeviceScope && (!this.store.deviceSelected || this.store.currentViewId === "select_device_prompt");

    return html`<aside class="sidebar">
      <div role="tablist" aria-label="Scope" class="scope-tabs">
        <button
          type="button"
          id="tab-scope-device"
          role="tab"
          aria-selected=${isDeviceScope ? "true" : "false"}
          tabindex=${isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.openDevicesLanding()}
          @keydown=${(ev: KeyboardEvent) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${isDeviceScope ? "active" : ""}"
        >
          Devices
        </button>
        <button
          type="button"
          id="tab-scope-system"
          role="tab"
          aria-selected=${!isDeviceScope ? "true" : "false"}
          tabindex=${!isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.setScope("system")}
          @keydown=${(ev: KeyboardEvent) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${!isDeviceScope ? "active" : ""}"
        >
          System
        </button>
      </div>

      ${!isDeviceScope
        ? html`<nav id="nav-scope-system" aria-label="System pages" class="nav-list">
            ${SYSTEM_NAV_ITEMS.map((item) => {
              const active = this.store.currentViewId === item.viewId;
              return html`<button
                type="button"
                data-view=${item.viewId}
                aria-current=${active ? "page" : nothing}
                @click=${() => this.store.switchView(item.viewId)}
                class="nav-btn ${active ? "active" : ""}"
              >
                <span>${item.label}</span>
              </button>`;
            })}
          </nav>`
        : this.store.deviceSelected && this.store.currentViewId !== "select_device_prompt"
          ? this._renderDeviceNav()
          : html`<nav id="nav-scope-devices-list" aria-label="Devices" class="nav-list">
              <button
                type="button"
                data-view="select_device_prompt"
                aria-current=${allDevicesActive ? "page" : nothing}
                @click=${() => this.store.openDevicesLanding()}
                class="nav-btn ${allDevicesActive ? "active" : ""}"
              >
                <span>All Devices</span>
                <span id="nav-system-count" class="nav-badge">${this.store.state ? String(deviceCount) : "—"}</span>
              </button>
            </nav>`}
    </aside>`;
  }

  protected override render(): TemplateResult {
    const data = this.store.state;
    const isInitialLoading = this.store.loading && !data && !this.store.loadError && !this.store.studioRevMismatch;
    const showHeaderUpdate =
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      Boolean(data?.live?.fw_update_available && data?.live?.fw_update_entity);

    const subtitle = this.store.pageSubtitle;

    return html`<div
      id="studio-root"
      class="studio-root ${isInitialLoading ? "is-loading" : ""}"
    >
      ${this.store.studioRevMismatch
        ? html`<div role="status" class="studio-rev-banner">
            <span>Latter Studio was updated — Reload Page</span>
            <button
              type="button"
              @click=${() => this.store.reloadPage()}
              class="btn btn-primary btn-compact"
            >
              Reload Page
            </button>
          </div>`
        : nothing}

      <header class="latter-top-titlebar">
        <div class="titlebar-brand">
          <button
            type="button"
            aria-label="Toggle the Home Assistant sidebar"
            @click=${() => this.store.toggleParentHaSidebar()}
            class="btn-icon ha-menu-btn"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z" />
            </svg>
          </button>
          <span class="titlebar-title">Latter</span>
        </div>
        <div class="titlebar-actions">
          ${showHeaderUpdate
            ? html`<button
                type="button"
                id="hdr-update-pill"
                @click=${() => void this.store.triggerHeaderFirmwareUpdate()}
                class="btn btn-secondary btn-compact"
              >
                Install Update
              </button>`
            : nothing}
        </div>
      </header>

      <div class="app-shell">
        ${this._renderSidebar()}

        <main
          class="main-area"
          @focusout=${() => void this.store.flushAllPendingSettings()}
        >
          <div class="content-wrap">
            <h2 id="unified-page-title" class="page-title">
              <span>${this.store.pageTitle}</span>
              ${subtitle ? html`<span class="page-subtitle">${subtitle}</span>` : nothing}
            </h2>

            ${isInitialLoading
              ? html`<div id="studio-loading" role="status" class="loading-state">
                  Loading Latter…
                </div>`
              : nothing}

            ${!data && this.store.loadError
              ? html`<div id="studio-load-error" role="alert" class="alert alert-error">
                  <span id="studio-load-error-text">${this.store.loadError}</span>
                  <button
                    type="button"
                    @click=${() => void this.store.refreshState()}
                    class="btn btn-secondary btn-compact"
                  >
                    Retry
                  </button>
                </div>`
              : nothing}

            ${data ? renderActiveView(this.store) : nothing}
          </div>
        </main>
      </div>

      ${renderStudioDialogs(this.store)}

      ${this.store.toastMessage
        ? html`<div
            role="status"
            aria-live="polite"
            class="toast ${this.store.toastIsError ? "error" : ""}"
          >
            ${this.store.toastMessage}
          </div>`
        : nothing}
    </div>`;
  }
}

if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
