/**
 * Latter Studio Design System Tokens & Stylesheet (`docs/studio-design.md` §3).
 * Literal font sizes, pixel spacing, and colors appear ONLY inside the single `:host` block.
 */

import { css } from "../lib/lit.js";

export const STUDIO_STYLES = css`
  :host {
    /* Design tokens (docs/studio-design.md section 3). Every visual value reads a token; each token
       reads a Home Assistant theme variable, with a fallback for themes that do not set it. */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.6);
    --studio-line-height-condensed: var(--ha-line-height-condensed, 1.2);
    --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
    --studio-card-title-tracking: -0.012em;
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-card-top: var(--ha-space-5, 20px);
    --studio-space-5: var(--ha-space-6, 24px);
    --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-field: var(--ha-border-radius-sm, 4px);
    --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
    --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-card-border-width: var(--ha-card-border-width, 1px);
    --studio-control-height: var(--ha-button-height, 40px);
    --studio-control-height-compact: 32px;
    --studio-row-min-height: 56px;
    --studio-header-height: var(--header-height, 56px);
    --studio-sidebar-width: 244px;
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #282828);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #9b9b9b));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, rgba(255, 255, 255, 0.05));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #363636));
    --studio-field-bg-hover: var(--ha-color-form-background-hover, var(--studio-field-bg));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(255, 255, 255, 0.42)));
    --studio-popup-bg: var(--card-background-color, #1c1c1c);
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #9b9b9b);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #009ac7);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 0, 154, 199), 0.12);
    --studio-primary-tint-strong: rgba(var(--rgb-primary-color, 0, 154, 199), 0.24);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);
    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, var(--primary-color, #009ac7));
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, var(--studio-btn-accent-bg));
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, var(--text-primary-color, #ffffff));
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint));
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, var(--studio-primary-tint-strong));
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, var(--primary-color, #009ac7));
    --studio-btn-plain-hover: var(--ha-color-fill-primary-quiet-resting, var(--studio-primary-tint));
    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, var(--studio-error-tint));
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, var(--error-color, #db4437));
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, var(--error-color, #db4437));
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);
    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #202020));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #989898));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint-strong)));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, var(--primary-color, #009ac7)));
    --studio-switch-thumb-shadow: var(--ha-switch-thumb-box-shadow, var(--ha-box-shadow-s, 0 1px 2px rgba(0, 0, 0, 0.3)));
    --studio-toast-bg: var(--primary-text-color, #e1e1e1);
    --studio-toast-text: var(--card-background-color, #1c1c1c);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(110, 110, 110));
    --studio-success: var(--success-color, #43a047);
    --studio-warning: var(--warning-color, #ffa600);
    --studio-error: var(--error-color, #db4437);
    --studio-info: var(--info-color, #039be5);
    --studio-success-tint: color-mix(in srgb, var(--studio-success) 14%, transparent);
    --studio-warning-tint: color-mix(in srgb, var(--studio-warning) 14%, transparent);
    --studio-error-tint: color-mix(in srgb, var(--studio-error) 14%, transparent);
    --studio-info-tint: color-mix(in srgb, var(--studio-info) 14%, transparent);
    --studio-card-shadow: var(--ha-card-box-shadow, none);
    --studio-overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --studio-scrim: rgba(0, 0, 0, 0.5);
    --studio-media-bg: var(--secondary-background-color, #000000);
    display: block;
    min-height: 100vh;
    background: var(--studio-bg);
    color: var(--studio-text);
    font-family: var(--studio-font-family);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
    color-scheme: light;
    scrollbar-color: var(--studio-scrollbar-thumb) transparent;
    scrollbar-width: thin;
  }
  :host([dark]) { color-scheme: dark; }
  * { box-sizing: border-box; }
  .hidden { display: none !important; }
  .studio-root {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--studio-bg);
  }
  h2, h3, h4, p { margin: 0; }
  code, .mono {
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* ---------- Upgrade banner ---------- */
  .studio-rev-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    background: var(--studio-warning-tint);
    border-bottom: 1px solid var(--studio-warning);
    color: var(--studio-text);
    z-index: 40;
  }

  /* ---------- Title bar ---------- */
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding: 0 var(--studio-space-3);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-bottom: var(--studio-header-border);
    position: sticky;
    top: 0;
    z-index: 30;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
    user-select: none;
  }
  .titlebar-brand .ha-menu-btn { color: var(--studio-header-icon); display: none; }
  :host([narrow]) .titlebar-brand .ha-menu-btn { display: inline-flex; }
  .titlebar-title { padding-inline-start: var(--studio-space-3); }
  :host([narrow]) .titlebar-title { padding-inline-start: 0; }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }

  /* ---------- Shell & navigation ---------- */
  .app-shell {
    display: grid;
    grid-template-columns: var(--studio-sidebar-width) minmax(0, 1fr);
    min-height: calc(100vh - var(--studio-header-height));
  }
  aside.sidebar {
    background: var(--studio-sidebar-bg);
    border-right: 1px solid var(--studio-divider);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-4) var(--studio-space-3);
    position: sticky;
    top: var(--studio-header-height);
    height: calc(100vh - var(--studio-header-height));
    overflow-y: auto;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    background: var(--studio-input-bg);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .scope-tab {
    min-height: var(--studio-control-height-compact);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .scope-tab.active {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    width: 100%;
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
  }
  .nav-btn:hover { background: var(--studio-hover); }
  .nav-btn.active {
    background: var(--studio-primary-tint);
    color: var(--studio-primary);
  }
  .nav-btn.nav-back-btn { color: var(--studio-text-secondary); }
  .nav-device-title {
    padding: var(--studio-space-2) var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    border-bottom: 1px solid var(--studio-divider);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-4); }
  .nav-badge {
    min-width: 20px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .main-area { min-width: 0; }
  .content-wrap {
    max-width: 1140px;
    margin: 0 auto;
    padding: var(--studio-space-5) var(--studio-space-5) var(--studio-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    container-type: inline-size;
    container-name: studio-content;
  }
  .content-wrap > section {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
  }
  .page-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
  }
  .page-subtitle {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .is-loading .content-wrap > section { display: none !important; }
  .columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-4);
    align-items: start;
  }
  .column {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    min-width: 0;
  }
  @container studio-content (max-width: 760px) {
    .columns { grid-template-columns: minmax(0, 1fr); }
  }

  /* ---------- Card ---------- */
  .card {
    min-width: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: var(--studio-card-border-width) solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
    color: var(--studio-text);
  }
  .card.danger { border-color: var(--studio-error); }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-card-top) var(--studio-space-4) 0;
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    min-width: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    letter-spacing: var(--studio-card-title-tracking);
    line-height: var(--studio-line-height-condensed);
  }
  .card-subtitle, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .card-header-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .card-content {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-4);
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-bottom: var(--studio-space-card-top);
  }
  details.card > summary::-webkit-details-marker { display: none; }
  details.card > summary::after {
    content: "▾";
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.card[open] > summary::after { transform: rotate(180deg); }
  details.card[open] > summary { border-bottom: 1px solid var(--studio-divider); }
  details.sub-collapsible {
    border-top: 1px solid var(--studio-divider);
    padding-top: var(--studio-space-3);
  }
  details.sub-collapsible > summary {
    cursor: pointer;
    font-weight: var(--studio-weight-medium);
  }
  details.sub-collapsible > .card-content { padding: var(--studio-space-3) 0 0; }
  .fusion-area { border-bottom: 1px solid var(--studio-divider); padding-bottom: var(--studio-space-3); }
  .fusion-area:last-child { border-bottom: none; }
  .fusion-area > .settings-row { border-bottom: none; }
  .subsection-title {
    padding-top: var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }
  .card-content > .subsection-title:first-child { padding-top: 0; border-top: none; }

  /* ---------- Settings row & controls ---------- */
  .settings-list {
    display: flex;
    flex-direction: column;
  }
  .settings-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--studio-space-4);
    min-height: var(--studio-row-min-height);
    padding: var(--studio-space-2) 0;
  }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .row-label { font-weight: var(--studio-weight-regular); }
  .row-description { line-height: normal; }
  .settings-row-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .settings-row-control select,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="search"],
  .settings-row-control input[type="number"],
  .settings-row-control input[type="password"] {
    width: 260px;
    max-width: 100%;
  }
  .settings-row-control input[type="number"],
  .settings-row-control input[type="password"] { width: 140px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; width: auto; }
  select, input[type="text"], input[type="search"], input[type="number"], input[type="password"], textarea {
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-bottom: 1px solid var(--studio-field-line);
    border-radius: var(--studio-radius-field) var(--studio-radius-field) 0 0;
    background: var(--studio-field-bg);
    color: var(--studio-text);
    font: inherit;
    transition: background-color 0.15s ease-out;
  }
  textarea {
    padding: var(--studio-space-2) var(--studio-space-3);
    resize: vertical;
  }
  select:hover, input[type="text"]:hover, input[type="search"]:hover, input[type="number"]:hover, input[type="password"]:hover, textarea:hover { background: var(--studio-field-bg-hover); }
  select option, select optgroup { background-color: var(--studio-popup-bg); color: var(--studio-text); }
  input::placeholder, textarea::placeholder { color: var(--studio-text-secondary); opacity: 1; }
  input[readonly] { color: var(--studio-text-secondary); }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { width: 140px; accent-color: var(--studio-primary); }
  select:focus-visible, input:focus-visible, textarea:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  select:focus-visible, input[type="text"]:focus-visible, input[type="search"]:focus-visible, input[type="number"]:focus-visible, input[type="password"]:focus-visible, textarea:focus-visible {
    outline: none;
    border-bottom-color: var(--studio-primary);
    box-shadow: inset 0 -1px 0 var(--studio-primary);
  }
  .switch {
    appearance: none;
    position: relative;
    width: 48px;
    height: 24px;
    margin: 0;
    border: 1px solid var(--studio-switch-border);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-switch-track);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--studio-switch-thumb);
    box-shadow: var(--studio-switch-thumb-shadow);
    transition: transform 0.15s ease, background-color 0.15s ease;
  }
  .switch:checked { background: var(--studio-switch-on-track); border-color: var(--studio-switch-on-border); }
  .switch:checked::after { transform: translateX(24px); background: var(--studio-switch-on-thumb); }
  .switch:disabled { opacity: 0.3; cursor: not-allowed; }
  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input:not([type="file"]), .input-action-row > select { flex: 1 1 180px; min-width: 0; }
  .input-action-row > input[type="file"] { flex: 0 1 auto; max-width: 100%; }
  .segmented {
    display: inline-flex;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
  }
  .segmented button {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .segmented button[aria-checked="true"] { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .inline-switch { display: inline-flex; align-items: center; gap: var(--studio-space-2); cursor: pointer; white-space: nowrap; }
  .list-row {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-main {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--studio-space-2);
    flex: 1;
    min-width: 0;
  }
  .list-row-grow { flex: 1; min-width: 0; }
  .list-block {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-head {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
  }
  .stacked-field {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .stacked-field > label, .stacked-field > .field-label {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .stacked-field > select, .stacked-field > input { width: 100%; }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }

  /* ---------- Buttons ---------- */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-4);
    border: none;
    border-radius: var(--studio-radius-button);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease-out;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-btn-accent-bg); color: var(--studio-btn-accent-text); }
  .btn-primary:hover:not(:disabled) { background: var(--studio-btn-accent-bg-hover); }
  .btn-secondary { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .btn-secondary:hover:not(:disabled) { background: var(--studio-btn-tonal-bg-hover); }
  .btn-text {
    background: transparent;
    color: var(--studio-btn-tonal-text);
    padding: 0 var(--studio-space-3);
  }
  .btn-text:hover:not(:disabled) { background: var(--studio-btn-plain-hover); }
  .btn-danger { background: var(--studio-danger-tonal-bg); color: var(--studio-danger-tonal-text); }
  .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
  .btn-danger-filled { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .btn-icon:hover { background: var(--studio-hover); }
  .btn-icon.danger { color: var(--studio-error); }
  .btn-icon svg { width: 20px; height: 20px; fill: currentColor; }
  .quick-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
    padding-bottom: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
  }
  .quick-action-grid:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
  .quick-action-btn {
    justify-content: flex-start;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-2) var(--studio-space-3);
    border-radius: var(--studio-radius-control);
    white-space: normal;
    text-align: left;
    line-height: var(--studio-line-height-condensed);
  }
  .quick-action-btn svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
    flex-shrink: 0;
  }

  /* ---------- Data display ---------- */
  .kv-list { display: flex; flex-direction: column; gap: 0; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-1) 0;
  }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  button.kv-row {
    width: 100%;
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  button.kv-row:hover { background: var(--studio-hover); }
  button.kv-row > strong::after {
    content: " ›";
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  table.data-table th {
    padding: 0;
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  .sort-btn {
    width: 100%;
    padding: var(--studio-space-3) var(--studio-space-3);
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: left;
    cursor: pointer;
  }
  .sort-btn:hover { color: var(--studio-text); }
  th[aria-sort="ascending"] .sort-btn, th[aria-sort="descending"] .sort-btn { color: var(--studio-primary); }
  table.data-table td {
    padding: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  table.data-table tbody tr:last-child td { border-bottom: none; }
  table.data-table tbody tr { cursor: pointer; }
  table.data-table tbody tr:hover, table.data-table tbody tr:focus-visible { background: var(--studio-hover); }
  td.col-name { font-weight: var(--studio-weight-medium); }
  td.col-open { color: var(--studio-text-secondary); text-align: right; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: 22px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .chip-primary { background: var(--studio-primary-tint); color: var(--studio-primary); }
  .chip-success { background: var(--studio-success-tint); color: var(--studio-success); }
  .chip-warning { background: var(--studio-warning-tint); color: var(--studio-warning); }
  .chip-error { background: var(--studio-error-tint); color: var(--studio-error); }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    margin-right: var(--studio-space-2);
    border-radius: 50%;
    background: var(--studio-text-disabled);
  }
  .chip > .status-dot { margin-right: var(--studio-space-1); }
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }
  .status-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
  }
  @media (max-width: 480px) {
    .status-tiles { grid-template-columns: minmax(0, 1fr); }
  }
  .status-tile {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-1);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: left;
  }
  button.status-tile {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.status-tile:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  button.status-tile:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .status-tile-head {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile-head svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .status-tile-value {
    margin-top: var(--studio-space-1);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .status-tile-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile > .signal-track { margin-top: var(--studio-space-1); }
  .status-assignments {
    padding-top: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  .status-assignments strong {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--studio-space-2);
  }
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .pill.enabled {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    color: var(--studio-text);
  }
  .pill-move {
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    padding: 0 var(--studio-space-1);
    cursor: pointer;
  }
  .pill-move:hover { color: var(--studio-primary); }
  .pill-toggle {
    padding: 0;
    border: none;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .swatch {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* ---------- BLE rows & upload progress ---------- */
  .signal-row {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .signal-row.winner { border-color: var(--studio-primary); }
  .signal-row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-row-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-meta { color: var(--studio-text-secondary); font-size:var(--studio-font-secondary); }
  .signal-track, .upload-progress {
    height: 6px;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface-alt);
    overflow: hidden;
  }
  .signal-fill {
    width: var(--signal-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.25s ease;
  }
  .signal-fill.low { background: var(--studio-error); }
  .upload-progress-fill {
    width: var(--upload-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.15s ease;
  }

  /* ---------- Wallpapers ---------- */
  .wp-upload-trigger {
    display: inline-flex;
    align-items: center;
  }
  .wp-upload-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
  }
  .wp-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--studio-space-3);
  }
  .wp-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    text-align: center;
  }
  .wp-gallery > .empty-state { grid-column: 1 / -1; }
  .wp-card.active { border-color: var(--studio-primary); background: var(--studio-primary-tint); }
  .wp-thumb-btn {
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--studio-radius-control);
    cursor: pointer;
    line-height: 0;
  }
  .wp-thumb-btn.circle { border-radius: 50%; }
  .wp-thumb-btn:hover .wp-thumb { border-color: var(--studio-primary); }
  .wp-thumb-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .wp-thumb {
    width: 104px;
    height: 104px;
    object-fit: cover;
    background: var(--studio-media-bg);
    border: 1px solid var(--studio-divider);
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: var(--studio-radius-control); }
  .wp-title {
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    overflow-wrap: anywhere;
  }
  .wp-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    margin-top: auto;
    width: 100%;
  }
  .btn-icon.wp-star-btn {
    width: var(--studio-control-height-compact);
    height: var(--studio-control-height-compact);
  }
  .btn-icon.wp-star-btn:hover {
    color: var(--studio-warning);
    background: var(--studio-warning-tint);
  }
  .btn-icon.wp-star-btn.starred {
    color: var(--studio-warning);
  }
  .cam-preview {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .cam-preview img {
    width: 100%;
    max-width: 360px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
  }
  .log-output {
    max-height: 380px;
    margin: 0;
    padding: var(--studio-space-3);
    overflow: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    white-space: pre-wrap;
  }

  /* ---------- States ---------- */
  .empty-state {
    padding: var(--studio-space-3) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-5) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state::before {
    content: "";
    width: 20px;
    height: 20px;
    border: 2px solid var(--studio-divider);
    border-top-color: var(--studio-primary);
    border-radius: 50%;
    animation: studio-spin 0.8s linear infinite;
  }
  .studio-root:not(.is-loading) #studio-loading { display: none; }
  @keyframes studio-spin { to { transform: rotate(360deg); } }
  .alert {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-info-tint);
  }
  .alert-error { background: var(--studio-error-tint); }
  .alert-warning { background: var(--studio-warning-tint); }
  .alert-body { display: flex; flex-direction: column; gap: var(--studio-space-1); min-width: 0; }
  .alert-list { margin: 0; padding-left: var(--studio-space-5); }
  .toast {
    position: fixed;
    left: 50%;
    bottom: var(--studio-space-5);
    transform: translateX(-50%);
    z-index: 50;
    max-width: min(560px, calc(100vw - 32px));
    padding: var(--studio-space-3) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-toast-bg);
    color: var(--studio-toast-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  .toast.error { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .offscreen { position: fixed; top: -9999px; left: -9999px; }

  /* ---------- Dialogs ---------- */
  dialog.studio-dialog {
    width: min(460px, calc(100vw - 32px));
    padding: var(--studio-space-5);
    border: none;
    border-radius: var(--studio-radius-dialog);
    background: var(--studio-surface);
    color: var(--studio-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  dialog.studio-dialog::backdrop { background: var(--studio-scrim); }
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .dialog-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height-condensed);
  }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--studio-space-2);
    margin-top: var(--studio-space-2);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input[type="text"] { width: 120px; font-family: var(--studio-font-code); text-align: center; }
  .color-hex-row input[type="color"] {
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: none;
    cursor: pointer;
  }

  /* ---------- Narrow cards and screens ---------- */
  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @container (max-width: 360px) {
    .quick-action-grid { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .titlebar-title { padding-inline-start: 0; }
    .app-shell { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
    aside.sidebar {
      align-self: start;
      position: sticky;
      top: var(--studio-header-height);
      z-index: 25;
      height: auto;
      padding: var(--studio-space-2) var(--studio-space-3);
      border-right: none;
      border-bottom: 1px solid var(--studio-divider);
    }
    .nav-device-title { display: none; }
    .nav-list { flex-direction: row; overflow-x: auto; scrollbar-width: none; }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn { width: auto; border: 1px solid var(--studio-divider); border-radius: var(--studio-radius-pill); }
    #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-3); }
    .content-wrap { padding: var(--studio-space-4) var(--studio-space-3) var(--studio-space-5); }
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @media (max-width: 480px) {
    .list-row { flex-wrap: wrap; }
    .list-row-head { flex-wrap: wrap; }
    .list-row-main { grid-template-columns: minmax(0, 1fr); width: 100%; }
  }
`;
