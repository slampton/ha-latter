/**
 * `<latter-studio>` Custom Element — Modular TypeScript + Stock `lit` Shell (`D-023`, `D-061`, `D-062`, `D-078`).
 *
 * - Zero `window.*` property bindings; state is owned per element by `StudioStore`.
 * - `_applyRoute()` runs before `super.connectedCallback()` so `hostConnected` subscribes once.
 * - Sidebar `<a href="/latter/...">` links with `aria-current="page"` and SPA click interception.
 * - Promoted `<h1>` `#unified-page-title`, persistent polite/assertive live regions, sticky error toast,
 *   `.loading-state` skeleton during `store.deviceLoading`, and shared `renderConfirmDialog`.
 */

import { renderConfirmDialog, syncDialogElement } from "./components/controls.js";
import { renderStudioDialogs, syncStudioDialogs } from "./components/dialogs.js";
import { DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS } from "./constants.js";
import type { StudioTranslationKey } from "./i18n/index.js";
import {
  html,
  LitElement,
  nothing,
  type PropertyValues,
  type TemplateResult,
} from "./lib/lit.js";
import { StudioStore } from "./state/store.js";
import { STUDIO_STYLES } from "./styles/tokens.js";
import type { DeviceViewId, HassRoute, HomeAssistant, SystemViewId } from "./types.js";
import { renderActiveView } from "./views/index.js";

const SYSTEM_NAV_ITEMS: ReadonlyArray<{
  viewId: SystemViewId;
  labelKey: StudioTranslationKey;
}> = [
  { viewId: "system_overview", labelKey: "view.system_overview" },
  { viewId: "shared_entities", labelKey: "view.shared_entities" },
  { viewId: "photos", labelKey: "view.photos" },
  { viewId: "remotes", labelKey: "view.remotes" },
  { viewId: "system_sync", labelKey: "view.system_sync" },
  { viewId: "area_tracking", labelKey: "view.area_tracking" },
  { viewId: "system_tools", labelKey: "view.system_tools" },
];

const DEVICE_NAV_ITEMS: ReadonlyArray<{
  viewId: Exclude<DeviceViewId, "select_device_prompt" | "discovered_devices">;
  labelKey: StudioTranslationKey;
  id?: string;
}> = [
  { viewId: "dashboard", labelKey: "view.dashboard" },
  { viewId: "display", labelKey: "view.display", id: "nav-btn-display" },
  { viewId: "interface", labelKey: "view.interface", id: "nav-btn-interface" },
  { viewId: "audio_voice", labelKey: "view.audio_voice", id: "nav-btn-audio_voice" },
  { viewId: "power", labelKey: "view.power", id: "nav-btn-power" },
  { viewId: "presence", labelKey: "view.presence" },
  { viewId: "tools", labelKey: "view.tools" },
];

export class LatterStudio extends LitElement {
  static override styles = STUDIO_STYLES;

  readonly store: StudioStore;

  private _narrow = false;
  private _dark: boolean | null = null;
  private _showMenu: boolean | null = null;
  private _route: HassRoute | null = null;
  private _panel: Record<string, unknown> | null = null;
  private _routeInitialized = false;
  private _lastRouteHeadingKey = "";

  constructor() {
    super();
    this.store = new StudioStore(this);
    this.addController(this.store);
  }

  override connectedCallback(): void {
    if (!this._routeInitialized) {
      this._routeInitialized = true;
      this._applyRoute();
    }
    super.connectedCallback();
  }

  private _syncShowMenu(h: HomeAssistant | null): void {
    const show = this._narrow || h?.dockedSidebar === "always_hidden";
    if (this._showMenu !== show) {
      this._showMenu = show;
      this.toggleAttribute("show-menu", show);
    }
  }

  set hass(h: HomeAssistant | null) {
    const dark = Boolean(h?.themes?.darkMode);
    if (this._dark !== dark) {
      this._dark = dark;
      this.toggleAttribute("dark", dark);
    }
    this._syncShowMenu(h);
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
    this._syncShowMenu(this.store.hass);
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

  private _onNavLinkClick(ev: MouseEvent, navigate: () => void): void {
    if (
      ev.defaultPrevented ||
      ev.button !== 0 ||
      ev.metaKey ||
      ev.ctrlKey ||
      ev.shiftKey ||
      ev.altKey
    ) {
      return;
    }
    ev.preventDefault();
    navigate();
  }

  private _onRootKeyDown(ev: KeyboardEvent): void {
    if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.key === "Escape" || ev.key === "Tab") {
      return;
    }
    const path = typeof ev.composedPath === "function" ? ev.composedPath() : [];
    const inner = (path[0] ?? ev.target) as Element | null;
    if (!inner || typeof inner.tagName !== "string") return;
    const tag = inner.tagName.toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      ev.stopPropagation();
    }
  }

  private _onMainFocusOut(ev: FocusEvent): void {
    const path = typeof ev.composedPath === "function" ? ev.composedPath() : [];
    const target = (path[0] ?? ev.target) as Element | null;
    if (!target || typeof target.tagName !== "string") return;
    if (target.getAttribute("role") === "combobox") return;
    const tag = target.tagName.toUpperCase();
    if (tag === "TEXTAREA") {
      void this.store.entity.flushAllPendingSettings();
      return;
    }
    if (tag === "INPUT") {
      const type = String((target as HTMLInputElement).type || "text").toLowerCase();
      if (
        type === "text" ||
        type === "number" ||
        type === "search" ||
        type === "password" ||
        type === "tel" ||
        type === "url" ||
        type === "email"
      ) {
        void this.store.entity.flushAllPendingSettings();
      }
    }
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

  protected override updated(_changedProperties: PropertyValues): void {
    const root = this.renderRoot as ShadowRoot;
    syncStudioDialogs(root, this.store);
    const confirmDlg = root.getElementById(
      "latter-confirm-modal",
    ) as HTMLDialogElement | null;
    syncDialogElement(confirmDlg, this.store.confirmModal.open);

    const routeKey = `${this.store.currentScope}|${this.store.currentViewId}|${this.store.activeSubentryId}`;
    if (this._lastRouteHeadingKey && this._lastRouteHeadingKey !== routeKey) {
      const titleText = this.store.pageSubtitle
        ? `${this.store.pageTitle} — ${this.store.pageSubtitle}`
        : this.store.pageTitle;
      this.store.announcePolite(titleText);
      const activeEl = root.activeElement as HTMLElement | null;
      if (activeEl && activeEl.classList?.contains("nav-btn")) {
        const headingEl = root.getElementById(
          "unified-page-title",
        ) as HTMLElement | null;
        headingEl?.focus?.({ preventScroll: true });
      }
    }
    this._lastRouteHeadingKey = routeKey;
  }

  private _renderDeviceNav(): TemplateResult {
    const subId = this.store.activeSubentryId;
    const encodedSub = encodeURIComponent(subId);
    const devTitle = this.store.pageSubtitle || this.store.t("common.unknown");
    const items = DEVICE_NAV_ITEMS.filter((item) => this.store.deviceHasView(item.viewId));

    return html`<nav
      id="nav-scope-device"
      aria-label=${this.store.t("nav.device_pages_label")}
      class="nav-list"
    >
      <a
        href="/latter/devices"
        @click=${(ev: MouseEvent) =>
          this._onNavLinkClick(ev, () => this.store.openDevicesLanding())}
        class="nav-btn nav-back-btn"
      >
        <span>${this.store.t("nav.back_managed")}</span>
      </a>
      <div id="nav-selected-device-label" class="nav-device-title">
        ${devTitle}
      </div>
      ${items.map((item) => {
        const active = this.store.currentViewId === item.viewId;
        const slug = DEVICE_VIEW_SLUGS[item.viewId];
        return html`<a
          href="/latter/devices/${encodedSub}/${slug}"
          id=${item.id || nothing}
          data-view=${item.viewId}
          aria-current=${active ? "page" : nothing}
          @click=${(ev: MouseEvent) =>
            this._onNavLinkClick(ev, () => this.store.switchView(item.viewId))}
          class="nav-btn ${active ? "active" : ""}"
        >
          <span>${this.store.t(item.labelKey)}</span>
        </a>`;
      })}
    </nav>`;
  }

  private _renderSidebar(): TemplateResult {
    const isDeviceScope = this.store.currentScope === "device";
    const deviceCount = (this.store.state?.system_devices || []).length;
    const discoveredLatterCount = (this.store.state?.discovered_latter_devices || []).length;
    const isDeviceListScope =
      !this.store.deviceSelected ||
      this.store.currentViewId === "select_device_prompt" ||
      this.store.currentViewId === "discovered_devices";
    const managedActive =
      isDeviceScope && isDeviceListScope && this.store.currentViewId !== "discovered_devices";
    const discoveredActive = isDeviceScope && this.store.currentViewId === "discovered_devices";

    return html`<aside class="sidebar">
      <div role="tablist" aria-label=${this.store.t("nav.scope_label")} class="scope-tabs">
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
          ${this.store.t("nav.devices")}
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
          ${this.store.t("nav.system")}
        </button>
      </div>

      ${!isDeviceScope
        ? html`<nav
            id="nav-scope-system"
            aria-label=${this.store.t("nav.system_pages_label")}
            class="nav-list"
          >
            ${SYSTEM_NAV_ITEMS.map((item) => {
              const active = this.store.currentViewId === item.viewId;
              const slug = SYSTEM_VIEW_SLUGS[item.viewId];
              return html`<a
                href="/latter/system/${slug}"
                data-view=${item.viewId}
                aria-current=${active ? "page" : nothing}
                @click=${(ev: MouseEvent) =>
                  this._onNavLinkClick(ev, () => this.store.switchView(item.viewId))}
                class="nav-btn ${active ? "active" : ""}"
              >
                <span>${this.store.t(item.labelKey)}</span>
              </a>`;
            })}
          </nav>`
        : !isDeviceListScope
          ? this._renderDeviceNav()
          : html`<nav
              id="nav-scope-devices-list"
              aria-label=${this.store.t("nav.devices_list_label")}
              class="nav-list"
            >
              <a
                href="/latter/devices"
                data-view="select_device_prompt"
                aria-current=${managedActive ? "page" : nothing}
                @click=${(ev: MouseEvent) =>
                  this._onNavLinkClick(ev, () => this.store.openDevicesLanding())}
                class="nav-btn ${managedActive ? "active" : ""}"
              >
                <span>${this.store.t("nav.managed")}</span>
                <span id="nav-system-count" class="nav-badge">
                  ${this.store.state ? String(deviceCount) : this.store.t("common.unknown")}
                </span>
              </a>
              <a
                href="/latter/devices/discovered"
                data-view="discovered_devices"
                aria-current=${discoveredActive ? "page" : nothing}
                @click=${(ev: MouseEvent) =>
                  this._onNavLinkClick(ev, () => this.store.openDiscoveredDevices())}
                class="nav-btn ${discoveredActive ? "active" : ""}"
              >
                <span>${this.store.t("nav.discovered")}</span>
                ${discoveredLatterCount > 0
                  ? html`<span id="nav-discovered-count" class="nav-badge">
                      ${String(discoveredLatterCount)}
                    </span>`
                  : nothing}
              </a>
            </nav>`}
    </aside>`;
  }

  protected override render(): TemplateResult {
    const data = this.store.state;
    const isInitialLoading =
      this.store.loading && !data && !this.store.loadError && !this.store.studioRevMismatch;
    const isDevicePendingPayload =
      !isInitialLoading &&
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      this.store.deviceLoading;
    const showHeaderUpdate =
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      !this.store.deviceLoading &&
      this.store.currentViewId !== "select_device_prompt" &&
      this.store.currentViewId !== "discovered_devices" &&
      Boolean(data?.live?.fw_update_available && data?.live?.fw_update_entity);

    const subtitle = this.store.pageSubtitle;
    const cm = this.store.confirmModal;

    return html`<div
      id="studio-root"
      @keydown=${(ev: KeyboardEvent) => this._onRootKeyDown(ev)}
      class="studio-root ${isInitialLoading ? "is-loading" : ""}"
    >
      <div
        id="studio-live-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        class="sr-only"
      >
        ${this.store.politeAnnouncement}
      </div>
      <div
        id="studio-live-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        class="sr-only"
      >
        ${this.store.assertiveAnnouncement}
      </div>

      ${this.store.studioRevMismatch
        ? html`<div role="status" class="studio-rev-banner">
            <span>${this.store.t("shell.rev_updated_banner")}</span>
            <button
              type="button"
              @click=${() => this.store.reloadPage()}
              class="btn btn-primary btn-compact"
            >
              ${this.store.t("shell.reload_page")}
            </button>
          </div>`
        : nothing}

      <header class="latter-top-titlebar">
        <div class="titlebar-brand">
          <button
            type="button"
            aria-label=${this.store.t("shell.toggle_ha_sidebar")}
            @click=${() => this.store.toggleParentHaSidebar()}
            class="btn-icon ha-menu-btn"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z" />
            </svg>
          </button>
          <span class="titlebar-title">${this.store.t("shell.title")}</span>
        </div>
        <div class="titlebar-actions">
          ${showHeaderUpdate
            ? html`<button
                type="button"
                id="hdr-update-pill"
                @click=${() => void this.store.entity.triggerHeaderFirmwareUpdate()}
                class="btn btn-secondary btn-compact"
              >
                ${this.store.t("shell.install_update")}
              </button>`
            : nothing}
        </div>
      </header>

      <div class="app-shell">
        ${this._renderSidebar()}

        <main
          class="main-area"
          @focusin=${(ev: FocusEvent) => this.store.onMainFocusIn(ev)}
          @focusout=${(ev: FocusEvent) => this._onMainFocusOut(ev)}
        >
          <div class="content-wrap">
            <h1 id="unified-page-title" tabindex="-1" class="page-title">
              <span>${this.store.pageTitle}</span>
              ${subtitle ? html`<span class="page-subtitle">${subtitle}</span>` : nothing}
            </h1>

            ${isInitialLoading
              ? html`<div id="studio-loading" role="status" class="loading-state">
                  ${this.store.t("shell.loading")}
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
                    ${this.store.t("shell.retry")}
                  </button>
                </div>`
              : nothing}

            ${isDevicePendingPayload
              ? html`<div id="studio-device-loading" role="status" class="loading-state">
                  ${this.store.t("shell.loading_device")}
                </div>`
              : data
                ? renderActiveView(this.store)
                : nothing}
          </div>
        </main>
      </div>

      ${renderStudioDialogs(this.store)}
      ${renderConfirmDialog({
        id: "latter-confirm-modal",
        open: cm.open,
        title: cm.title,
        consequence: cm.consequence,
        blastRadiusCount: cm.blastRadiusCount,
        blastRadiusLabel: cm.blastRadiusLabel || undefined,
        confirmLabel: cm.confirmLabel || this.store.t("action.confirm"),
        cancelLabel: cm.cancelLabel || this.store.t("action.cancel"),
        danger: cm.danger,
        busy: cm.busy,
        confirmButtonId: "btn-confirm-modal-accept",
        onConfirm: () => void this.store.runConfirmedAction(),
        onCancel: () => this.store.closeConfirm(),
        onDownloadBackupFirst: cm.onDownloadBackupFirst
          ? () => void cm.onDownloadBackupFirst?.()
          : null,
        overlay: this.store.localeOverlay,
      })}

      ${this.store.toastMessage
        ? html`<div class="toast ${this.store.toastIsError ? "error" : ""}">
            <span>${this.store.toastMessage}</span>
            ${this.store.toastIsError
              ? html`<button
                  type="button"
                  aria-label=${this.store.t("shell.dismiss_toast")}
                  @click=${() => this.store.dismissToast()}
                  class="btn btn-text btn-compact"
                >
                  ${this.store.t("action.dismiss")}
                </button>`
              : nothing}
          </div>`
        : nothing}
    </div>`;
  }
}

if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
