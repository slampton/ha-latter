/**
 * Latter Studio — Native Home Assistant Custom Panel (`panel_custom` Web Component)
 * Zero external dependencies; communicates exclusively via admin-gated `websocket_api`.
 */

const STUDIO_STYLES = `
  :host {
    /* Design tokens (docs/studio-design.md section 3). Every visual value reads a token; each token
       reads a Home Assistant theme variable, with a fallback for themes that don't set it. */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.5);
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-5: var(--ha-space-6, 24px);
    --studio-radius-card: var(--ha-card-border-radius, 12px);
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-control-height: 36px;
    --studio-control-height-compact: 28px;
    --studio-header-height: 56px;
    --studio-sidebar-width: 244px;
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #202020);
    --studio-header-bg: var(--app-header-background-color, var(--secondary-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, var(--secondary-background-color, #141414));
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #9b9b9b);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #03a9f4);
    --studio-on-primary: var(--text-primary-color, #ffffff);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12);
    --studio-primary-tint-strong: rgba(var(--rgb-primary-color, 3, 169, 244), 0.24);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);
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
    font-size: var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
  }
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
    font-size: var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* ---------- Title bar ---------- */
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding: 0 var(--studio-space-4);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-bottom: 1px solid var(--studio-divider);
    position: sticky;
    top: 0;
    z-index: 30;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    font-size: var(--studio-font-title);
    font-weight: var(--studio-weight-medium);
    user-select: none;
  }
  .brand-logo {
    width: 22px;
    height: 22px;
    fill: var(--studio-primary);
    flex-shrink: 0;
  }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .titlebar-brand .ha-menu-btn { display: none; }
  :host([narrow]) .titlebar-brand .ha-menu-btn { display: inline-flex; }

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
    background: var(--studio-primary);
    color: var(--studio-on-primary);
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
    font-size: var(--studio-font-section);
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
    font-size: var(--studio-font-caption);
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
    font-size: var(--studio-font-title);
    font-weight: var(--studio-weight-medium);
  }
  .page-subtitle {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .is-loading .content-wrap > section { display: none !important; }
  .grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: var(--studio-space-4);
    align-items: start;
  }

  /* ---------- Card ---------- */
  .card {
    min-width: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: 1px solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
  }
  .card.danger { border-color: var(--studio-error); }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-4) var(--studio-space-4) 0;
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size: var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
  }
  .card.danger .card-title { color: var(--studio-error); }
  .card-description, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size: var(--studio-font-secondary);
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
    padding: var(--studio-space-3) var(--studio-space-4);
    border-top: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-bottom: var(--studio-space-4);
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
    font-size: var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }

  /* ---------- Settings row & controls ---------- */
  .settings-list {
    display: flex;
    flex-direction: column;
  }
  .settings-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3) 0;
    border-bottom: 1px solid var(--studio-divider);
  }
  .settings-row:last-child { border-bottom: none; }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .row-label { font-weight: var(--studio-weight-regular); }
  .settings-row-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .settings-row-control select,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="number"] {
    width: 260px;
    max-width: 100%;
  }
  .settings-row-control input[type="number"] { width: 120px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; width: auto; }
  select, input[type="text"], input[type="number"], input[type="password"] {
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: var(--studio-text);
    font: inherit;
  }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { width: 140px; accent-color: var(--studio-primary); }
  select:focus-visible, input:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .switch {
    appearance: none;
    position: relative;
    width: 36px;
    height: 20px;
    margin: 0;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-text-disabled);
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.15s ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--studio-on-primary);
    transition: transform 0.15s ease;
  }
  .switch:checked { background: var(--studio-primary); }
  .switch:checked::after { transform: translateX(16px); }
  .switch:disabled { opacity: 0.5; cursor: default; }
  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input, .input-action-row > select { flex: 1 1 180px; min-width: 0; }
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
  .segmented button[aria-checked="true"] { background: var(--studio-primary-tint-strong); color: var(--studio-primary); }
  .inline-switch { display: inline-flex; align-items: center; gap: var(--studio-space-2); cursor: pointer; white-space: nowrap; }
  .list-row {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    background: var(--studio-input-bg);
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
  .list-row-grow { flex: 1; }
  .list-block {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    background: var(--studio-input-bg);
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
    font-size: var(--studio-font-secondary);
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
    border: 1px solid transparent;
    border-radius: var(--studio-radius-control);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    cursor: pointer;
  }
  .btn:disabled { opacity: 0.5; cursor: default; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-primary); color: var(--studio-on-primary); }
  .btn-secondary {
    background: transparent;
    color: var(--studio-primary);
    border-color: var(--studio-divider);
  }
  .btn-secondary:hover:not(:disabled), .btn-text:hover:not(:disabled) { background: var(--studio-primary-tint); }
  .btn-text {
    background: transparent;
    color: var(--studio-primary);
    padding: 0 var(--studio-space-2);
  }
  .btn-danger {
    background: transparent;
    color: var(--studio-error);
    border-color: var(--studio-error);
  }
  .btn-danger:hover:not(:disabled) { background: var(--studio-error-tint); }
  .btn-danger-filled { background: var(--studio-error); color: var(--studio-on-primary); }
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

  /* ---------- Data display ---------- */
  .kv-list { display: flex; flex-direction: column; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) 0;
    border-bottom: 1px solid var(--studio-divider);
  }
  .kv-row:last-child { border-bottom: none; }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  button.kv-row {
    width: 100%;
    border: none;
    border-bottom: 1px solid var(--studio-divider);
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
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--studio-space-3);
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    padding: var(--studio-space-3) var(--studio-space-4);
    background: var(--studio-surface);
    border: 1px solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    min-width: 0;
  }
  .stat > span { color: var(--studio-text-secondary); font-size: var(--studio-font-secondary); }
  .stat > strong {
    font-size: var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
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
    font-size: var(--studio-font-caption);
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
    font-size: var(--studio-font-caption);
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
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }
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
    font-size: var(--studio-font-secondary);
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
  .swatch {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* ---------- BLE rows ---------- */
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
  .signal-meta { color: var(--studio-text-secondary); font-size: var(--studio-font-secondary); }
  .signal-track {
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
  .signal-fill.no-signal { opacity: 0.2; }

  /* ---------- Wallpapers ---------- */
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
  .wp-thumb {
    width: 104px;
    height: 104px;
    object-fit: cover;
    background: var(--studio-media-bg);
    border: 1px solid var(--studio-divider);
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: var(--studio-radius-control); }
  .wp-title { font-size: var(--studio-font-secondary); font-weight: var(--studio-weight-medium); }
  .wp-actions {
    display: flex;
    justify-content: center;
    gap: var(--studio-space-1);
    margin-top: auto;
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
    padding: var(--studio-space-3) var(--studio-space-4);
    border-left: 4px solid var(--studio-info);
    border-radius: var(--studio-radius-control);
    background: var(--studio-info-tint);
  }
  .alert-error { border-left-color: var(--studio-error); background: var(--studio-error-tint); }
  .alert-warning { border-left-color: var(--studio-warning); background: var(--studio-warning-tint); }
  .alert-body { display: flex; flex-direction: column; gap: var(--studio-space-1); min-width: 0; }
  .alert-list { margin: 0; padding-left: var(--studio-space-5); }
  .toast {
    position: fixed;
    right: var(--studio-space-5);
    bottom: var(--studio-space-5);
    z-index: 50;
    max-width: 420px;
    padding: var(--studio-space-3) var(--studio-space-4);
    border: 1px solid var(--studio-primary);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface);
    box-shadow: var(--studio-overlay-shadow);
    font-weight: var(--studio-weight-medium);
  }
  .toast.error { border-color: var(--studio-error); color: var(--studio-error); }
  .offscreen { position: fixed; top: -9999px; left: -9999px; }

  /* ---------- Dialogs ---------- */
  dialog.studio-dialog {
    width: min(460px, calc(100vw - 32px));
    padding: var(--studio-space-5);
    border: 1px solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
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
    font-size: var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
  }
  .dialog-title.danger { color: var(--studio-error); }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--studio-space-2);
    margin-top: var(--studio-space-2);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input { width: 120px; font-family: var(--studio-font-code); text-align: center; }

  /* ---------- Narrow cards and screens ---------- */
  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"] { width: 100%; }
  }
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .app-shell { grid-template-columns: 1fr; }
    aside.sidebar {
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
    .grid-2 { grid-template-columns: 1fr; }
    .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"] { width: 100%; }
  }
`;

const STUDIO_TEMPLATE = `<div class="studio-root is-loading" id="studio-root">
<header class="latter-top-titlebar">
  <div class="titlebar-brand">
    <button type="button" class="btn-icon ha-menu-btn" aria-label="Toggle the Home Assistant sidebar" onclick="toggleParentHaSidebar()">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z"/></svg>
    </button>
    <svg class="brand-logo" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h1A1.5 1.5 0 0 1 8 5.5v13A1.5 1.5 0 0 1 6.5 20h-1A1.5 1.5 0 0 1 4 18.5v-13ZM16 5.5A1.5 1.5 0 0 1 17.5 4h1A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-1A1.5 1.5 0 0 1 16 18.5v-13ZM4 16.5h16v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2ZM8 5.25h8v2.5H8v-2.5ZM8 10.75h8v2.5H8v-2.5Z"/></svg>
    <span>Latter</span>
  </div>
  <div class="titlebar-actions">
    <button type="button" id="hdr-update-pill" class="btn btn-secondary btn-compact hidden" onclick="triggerHeaderFirmwareUpdate()">Install update</button>
  </div>
</header>
<div class="app-shell">
  <aside class="sidebar">
    <div class="scope-tabs" role="tablist" aria-label="Scope">
      <button class="scope-tab active" id="tab-scope-device" role="tab" onclick="openDevicesLanding()">Devices</button>
      <button class="scope-tab" id="tab-scope-system" role="tab" onclick="setScope('system')">System</button>
    </div>

    <nav class="nav-list hidden" id="nav-scope-system" aria-label="System pages">
      <button class="nav-btn" data-view="system_overview" onclick="switchView('system_overview', this)"><span>System overview</span></button>
      <button class="nav-btn" data-view="shared_entities" onclick="switchView('shared_entities', this)"><span>Shared entities</span></button>
      <button class="nav-btn" data-view="remotes" onclick="switchView('remotes', this)"><span>Media &amp; remotes</span></button>
      <button class="nav-btn" data-view="system_sync" onclick="switchView('system_sync', this)"><span>Groups &amp; profiles</span></button>
      <button class="nav-btn" data-view="area_tracking" onclick="switchView('area_tracking', this)"><span>BLE &amp; Area presence</span></button>
      <button class="nav-btn" data-view="system_admin" onclick="switchView('system_admin', this)"><span>System settings</span></button>
    </nav>

    <nav class="nav-list" id="nav-scope-devices-list" aria-label="Devices">
      <button class="nav-btn active" data-view="select_device_prompt" onclick="openDevicesLanding()">
        <span>All Devices</span><span class="nav-badge" id="nav-system-count">—</span>
      </button>
    </nav>

    <nav class="nav-list hidden" id="nav-scope-device" aria-label="Device pages">
      <button class="nav-btn nav-back-btn" onclick="openDevicesLanding()"><span>&larr; All Devices</span></button>
      <div class="nav-device-title" id="nav-selected-device-label">—</div>
      <button class="nav-btn" data-view="dashboard" onclick="switchView('dashboard', this)"><span>Overview</span></button>
      <button class="nav-btn" id="nav-btn-home_display" data-view="home_display" onclick="switchView('home_display', this)"><span>Display &amp; home</span></button>
      <button class="nav-btn" id="nav-btn-audio_voice" data-view="audio_voice" onclick="switchView('audio_voice', this)"><span>Audio &amp; voice</span></button>
      <button class="nav-btn" id="nav-btn-power" data-view="power" onclick="switchView('power', this)"><span>Power &amp; battery</span></button>
      <button class="nav-btn" data-view="system" onclick="switchView('system', this)"><span>Device settings</span><span class="nav-badge" id="nav-esp-badge">—</span></button>
    </nav>
  </aside>

  <main class="main-area">
    <div class="content-wrap">
      <div class="page-header"><h2 class="page-title" id="unified-page-title">Devices</h2></div>
      <div id="studio-loading" class="loading-state" role="status">Loading Latter…</div>
      <div id="studio-load-error" class="alert alert-error hidden" role="alert">
        <span id="studio-load-error-text">Latter couldn't load.</span>
        <button type="button" class="btn btn-secondary btn-compact" onclick="refreshState(true)">Retry</button>
      </div>

      <!-- SYSTEM: SYSTEM OVERVIEW -->
      <section id="view-system_overview" class="hidden">
        <div class="card" id="card-issues">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Issues</h3>
              <p class="card-description">Latter's repairs, the same ones Home Assistant lists in Settings › Repairs.</p>
            </div>
            <div class="card-header-actions"><button type="button" class="btn btn-secondary btn-compact" onclick="openHaPage('/config/repairs')">Open Repairs</button></div>
          </div>
          <div class="card-content"><div id="sys-issues-list" class="settings-list"></div></div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-header">
              <div class="card-heading"><h3 class="card-title">System</h3><p class="card-description">Latter itself updates through HACS; the firmware check covers every Device.</p></div>
              <div class="card-header-actions"><button type="button" class="btn btn-secondary btn-compact" onclick="checkSystemUpdates()">Check firmware updates</button></div>
            </div>
            <div class="card-content kv-list">
              <div class="kv-row"><span>Latter version</span><strong id="sys-sum-version">—</strong></div>
              <button type="button" class="kv-row" onclick="openDevicesWithCategory('online')"><span>Online Devices</span><strong id="sys-sum-online">—</strong></button>
              <button type="button" class="kv-row" onclick="openDevicesWithCategory('native')"><span>Latter-native Devices</span><strong id="sys-sum-native">—</strong></button>
              <button type="button" class="kv-row" onclick="openDevicesWithCategory('ble_tracked')"><span>BLE-tracked Devices</span><strong id="sys-sum-ble-tracked">—</strong></button>
              <button type="button" class="kv-row" onclick="openDevicesWithCategory('assigned_person')"><span>Devices with an assigned person</span><strong id="sys-sum-people">—</strong></button>
              <button type="button" class="kv-row" onclick="openSystemSection('area_tracking', '')"><span>BLE Area proxies</span><strong id="sys-sum-proxies">—</strong></button>
            </div>
          </div>
          <div class="card">
            <div class="card-header"><div class="card-heading"><h3 class="card-title">Configured integrations</h3></div></div>
            <div class="card-content kv-list">
              <button type="button" class="kv-row" onclick="openSystemSection('remotes', 'card-remotes')"><span>Remote controls</span><strong id="sys-sum-remotes">—</strong></button>
              <button type="button" class="kv-row" onclick="openSystemSection('remotes', 'card-vol-overrides')"><span>Speaker volume overrides</span><strong id="sys-sum-vol">—</strong></button>
              <button type="button" class="kv-row" onclick="openSystemSection('shared_entities', 'card-cameras')"><span>Cameras</span><strong id="sys-sum-cameras">—</strong></button>
              <button type="button" class="kv-row" onclick="openSystemSection('shared_entities', 'card-calendars')"><span>Calendars</span><strong id="sys-sum-calendars">—</strong></button>
              <button type="button" class="kv-row" onclick="openSystemSection('system_sync', '')"><span>Groups &amp; saved profiles</span><strong id="sys-sum-groups-profiles">—</strong></button>
            </div>
          </div>
        </div>
      </section>

      <!-- SYSTEM: SHARED ENTITIES -->
      <section id="view-shared_entities" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Whole-home entities</h3>
              <p class="card-description">Shared entities used by the Home screen and the Whole-Home Hub.</p>
            </div></div>
            <div class="card-content settings-list">
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-weather_entity">Weather</label></div><div class="settings-row-control"><select id="cfg-weather_entity" onchange="saveField('system', this)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-alarm_entity">Security alarm</label></div><div class="settings-row-control"><select id="cfg-alarm_entity" onchange="saveField('system', this)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-thermostat_entity">Thermostat</label></div><div class="settings-row-control"><select id="cfg-thermostat_entity" onchange="saveField('system', this)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-lock_entity">Entry lock</label></div><div class="settings-row-control"><select id="cfg-lock_entity" onchange="saveField('system', this)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-garage_entity">Garage door</label></div><div class="settings-row-control"><select id="cfg-garage_entity" onchange="saveField('system', this)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-vacuum_entity">Robot vacuum</label></div><div class="settings-row-control"><select id="cfg-vacuum_entity" onchange="saveField('system', this)"></select></div></div>
            </div>
          </div>

          <div class="card" id="card-cameras">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Cameras &amp; doorbell audio</h3>
              <p class="card-description">Up to 10 cameras for the on-device Camera Carousel and doorbell popups. Devices can listen to a doorbell and reply by push-to-talk: your speech is transcribed and spoken on the camera's speaker with Home Assistant TTS.</p>
            </div></div>
            <div class="card-content">
              <div class="settings-list">
                <div class="settings-row">
                  <div class="settings-row-text"><label class="row-label" for="cfg-doorbell_noise_reduction">Doorbell audio noise reduction</label></div>
                  <div class="settings-row-control">
                    <select id="cfg-doorbell_noise_reduction" onchange="saveField('system', this)">
                      <option value="strong">Strong</option>
                      <option value="light">Light</option>
                      <option value="off">Off</option>
                    </select>
                  </div>
                </div>
                <div class="settings-row">
                  <div class="settings-row-text">
                    <label class="row-label" for="doorbell-test-device">Test the door speaker</label>
                    <p class="row-description">Speaks a test sentence on the primary camera's speaker, from the Device you choose.</p>
                  </div>
                  <div class="settings-row-control">
                    <select id="doorbell-test-device"></select>
                    <button type="button" class="btn btn-secondary" onclick="testDoorbellSpeaker()">Test</button>
                  </div>
                </div>
              </div>
              <div id="cameras-list" class="stack"></div>
              <div><button type="button" class="btn btn-text" onclick="addCameraRow('')">+ Add camera</button></div>
              <div id="cam-preview-box" class="cam-preview hidden">
                <div class="signal-row-head">
                  <strong id="cam-preview-label">Camera preview</strong>
                  <div class="input-action-row">
                    <button type="button" class="btn btn-secondary btn-compact" onclick="refreshActiveCameraPreview()">Refresh</button>
                    <button type="button" class="btn btn-text btn-compact" onclick="closeCameraPreviewBox()">Close</button>
                  </div>
                </div>
                <img id="cam-preview-img" alt="Camera snapshot">
              </div>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card" id="card-calendars">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Calendars</h3>
              <p class="card-description">Calendars merged into the on-device agenda and Home screen.</p>
            </div></div>
            <div class="card-content">
              <div id="calendars-list" class="stack"></div>
              <div><button type="button" class="btn btn-text" onclick="addCalendarRow('')">+ Add calendar</button></div>
            </div>
          </div>
        </div>
      </section>

      <!-- SYSTEM: MEDIA & REMOTES -->
      <section id="view-remotes" class="hidden">
        <div class="card" id="card-remotes">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Remote inventory</h3>
            <p class="card-description">Up to 10 <code>remote.*</code> or <code>media_player.*</code> entities. Organize them into remote groups below.</p>
          </div></div>
          <div class="card-content">
            <div id="remotes-list" class="stack"></div>
            <div><button type="button" class="btn btn-text" onclick="addRemoteControlRow('')">+ Add remote control</button></div>
          </div>
        </div>

        <div class="card" id="card-remote-groups">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Remote control groups</h3>
            <p class="card-description">Group remotes and assign a group to an Area (roaming Devices show that Area's remotes while they're in it) or to a Device.</p>
          </div></div>
          <div class="card-content">
            <div id="remote-groups-list" class="stack"></div>
            <div><button type="button" class="btn btn-text" onclick="addRemoteGroupRow()">+ Create remote group</button></div>
            <h4 class="subsection-title">Device remote assignment</h4>
            <div id="device-remote-assignments-list" class="settings-list"></div>
          </div>
        </div>

        <div class="card" id="card-vol-overrides">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Speaker volume overrides</h3>
            <p class="card-description">When audio plays on a speaker, send its volume changes to a different media player or number entity instead.</p>
          </div></div>
          <div class="card-content">
            <div id="volume-overrides-list" class="stack"></div>
            <div><button type="button" class="btn btn-text" onclick="addVolumeOverrideRow('', '')">+ Add volume override</button></div>
          </div>
        </div>
      </section>

      <!-- SYSTEM: GROUPS & PROFILES -->
      <section id="view-system_sync" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Configuration profiles</h3>
              <p class="card-description">Capture a Device's settings as a reusable profile, or apply a profile to any Device or group.</p>
            </div></div>
            <div class="card-content">
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="profile-source-device">Capture from</label></div><div class="settings-row-control"><select id="profile-source-device"></select></div></div>
                <div class="settings-row stacked"><div class="settings-row-text"><span class="row-label">Profile name and description</span></div>
                  <div class="settings-row-control"><input type="text" id="new-profile-name" placeholder="Profile name (e.g. Nightstand)"><input type="text" id="new-profile-desc" placeholder="Description (optional)"></div>
                </div>
              </div>
            </div>
            <div class="card-actions"><button type="button" class="btn btn-primary" onclick="captureDeviceProfile()">Capture profile</button></div>
            <div class="card-content">
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="profile-target-scope">Apply profiles to</label></div><div class="settings-row-control"><select id="profile-target-scope"></select></div></div>
              </div>
              <div id="saved-profiles-list" class="settings-list"></div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Device groups</h3>
              <p class="card-description">Groups target profiles and bulk controls.</p>
            </div></div>
            <div class="card-content">
              <div class="input-action-row">
                <input type="text" id="new-group-name" placeholder="New group name" aria-label="New group name">
                <input type="text" id="new-group-desc" placeholder="Description" aria-label="Group description">
                <button type="button" class="btn btn-secondary" onclick="createDeviceGroup()">Add group</button>
              </div>
              <div id="device-groups-list" class="settings-list"></div>
            </div>
          </div>
        </div>

        <details class="card">
          <summary class="card-header"><div class="card-heading">
            <h3 class="card-title">Bulk Device controls</h3>
            <p class="card-description">Change display, sleep, voice, or sound settings on several Devices at once.</p>
          </div></summary>
          <div class="card-content">
            <div class="list-row-main">
              <div class="stacked-field">
                <label for="group-ctrl-cat-filter">Category</label>
                <select id="group-ctrl-cat-filter" onchange="renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config)">
                  <option value="display">Display &amp; appearance</option>
                  <option value="sleep">Sleep &amp; wake</option>
                  <option value="voice">Voice assistant</option>
                  <option value="sound">Sound &amp; alerts</option>
                  <option value="music">Music &amp; media</option>
                  <option value="area">Area &amp; presence</option>
                  <option value="all">All categories</option>
                </select>
              </div>
              <div class="stacked-field">
                <label for="group-ctrl-filter">Target Devices</label>
                <select id="group-ctrl-filter" onchange="renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config)"></select>
              </div>
            </div>
            <div id="system-controls-list" class="settings-list"></div>
          </div>
        </details>
      </section>

      <!-- SYSTEM: BLE & AREA PRESENCE -->
      <section id="view-area_tracking" class="hidden">
        <div class="card">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Live Area presence &amp; sensor fusion</h3>
            <p class="card-description">Occupancy per Area (<code>binary_sensor.&lt;area&gt;_ble_occupancy</code>, <code>sensor.&lt;area&gt;_occupants</code>), combining BLE beacons with occupancy, mmWave and PIR sensors.</p>
          </div></div>
          <div class="card-content"><div id="area-presence-grid-box" class="settings-list"></div></div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Per-Area BLE signal calibration</h3>
              <p class="card-description">Choose a BLE-enabled Device, carry it into an Area, and select Calibrate current Area.</p>
            </div>
            <div class="card-header-actions">
              <select id="ble-survey-device-picker" aria-label="Calibration Device" onchange="onSelectBleSurveyDevice(this.value)"></select>
              <label class="inline-switch"><input type="checkbox" class="switch" role="switch" id="survey-fast-mode" onchange="toggleSurveyFastMode(this.checked)"><span>Fast refresh</span></label>
            </div>
          </div>
          <div class="card-content"><div id="rssi-container" class="stack"></div></div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Discovered nearby Bluetooth devices</h3>
              <p class="card-description">Adopt phones and watches (<code>private_ble_device</code>), iBeacons, or named BLE tags for Area tracking.</p>
            </div>
            <div class="card-header-actions"><button type="button" class="btn btn-secondary btn-compact" onclick="openAddDeviceModal()">Add by address</button></div>
          </div>
          <div class="card-content"><div id="ble-adopt-table-box" class="settings-list"></div></div>
        </div>
      </section>

      <!-- SYSTEM: SYSTEM SETTINGS -->
      <section id="view-system_admin" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Export settings</h3>
              <p class="card-description">Download the System's settings, or one Device's, as a JSON file. Full backups are Home Assistant's own; Latter's storage is in every Home Assistant backup.</p>
            </div></div>
            <div class="card-content settings-list">
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="bkp-scope-select">Export</label></div><div class="settings-row-control"><select id="bkp-scope-select"></select></div></div>
            </div>
            <div class="card-actions"><button type="button" class="btn btn-primary" onclick="exportBackupToComputer('')">Download</button></div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Restore from file</h3>
              <p class="card-description">Upload a <code>latter-*.json</code> export. A Device export can be restored onto a different Device.</p>
            </div></div>
            <div class="card-content settings-list">
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="bkp-upload-file">Backup file</label></div><div class="settings-row-control"><input type="file" id="bkp-upload-file" accept=".json,application/json"></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="bkp-restore-device">Device for a Device backup</label></div><div class="settings-row-control"><select id="bkp-restore-device"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="bkp-restore-esp">Restore the Device's own settings</label><p class="row-description">Selects, switches and numbers stored on the Device.</p></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="bkp-restore-esp" checked></div></div>
            </div>
            <div class="card-actions"><button type="button" class="btn btn-primary" onclick="restoreFromUploadedFile()">Restore</button></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card" id="card-announce">
            <div class="card-header"><div class="card-heading"><h3 class="card-title">Announcements &amp; Alerts</h3></div></div>
            <div class="card-content settings-list">
              <div class="settings-row">
                <div class="settings-row-text"><span class="row-label" id="announce-mode-label">Type</span></div>
                <div class="settings-row-control">
                  <div class="segmented" role="radiogroup" aria-labelledby="announce-mode-label">
                    <button type="button" role="radio" aria-checked="true" data-mode="notify" onclick="setAnnounceMode('notify')">Notification</button>
                    <button type="button" role="radio" aria-checked="false" data-mode="broadcast" onclick="setAnnounceMode('broadcast')">Broadcast</button>
                  </div>
                </div>
              </div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="announce-target">Send to</label></div><div class="settings-row-control"><select id="announce-target"></select></div></div>
              <div class="settings-row announce-notify-only"><div class="settings-row-text"><label class="row-label" for="announce-title">Title</label></div><div class="settings-row-control"><input type="text" id="announce-title" placeholder="e.g. Front door"></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="announce-message">Message</label><p class="row-description announce-broadcast-only hidden">Spoken with text-to-speech on the speakers.</p></div><div class="settings-row-control"><input type="text" id="announce-message" placeholder="e.g. Someone is at the front door"></div></div>
              <div class="settings-row announce-notify-only"><div class="settings-row-text"><label class="row-label" for="announce-priority">Priority</label></div><div class="settings-row-control">
                <select id="announce-priority"><option value="normal">Normal</option><option value="warning">Warning</option><option value="critical">Critical</option></select>
              </div></div>
              <div class="settings-row announce-notify-only"><div class="settings-row-text"><label class="row-label" for="announce-camera">Include a snapshot from the primary camera</label></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="announce-camera"></div></div>
            </div>
            <div class="card-actions"><button type="button" class="btn btn-primary" onclick="sendAnnouncement()">Send</button></div>
          </div>

          <div class="card" id="sys-custom-palettes-card">
            <div class="card-header">
              <div class="card-heading">
                <h3 class="card-title">Custom color library</h3>
                <p class="card-description">Saved theme colors. Apply one to a Device from its Display &amp; home page.</p>
              </div>
              <div class="card-header-actions"><button type="button" class="btn btn-secondary btn-compact" onclick="openColorWheelModal('system')">Add color</button></div>
            </div>
            <div class="card-content"><div id="sys-custom-palettes-list" class="settings-list"></div></div>
          </div>
        </div>

        <details class="card">
          <summary class="card-header"><div class="card-heading">
            <h3 class="card-title">System &amp; Device logs</h3>
            <p class="card-description">Latter's events plus Latter, ESPHome and Music Assistant entries from the Home Assistant log.</p>
          </div></summary>
          <div class="card-content">
            <div class="input-action-row">
              <button type="button" class="btn btn-secondary btn-compact" onclick="openNativeHaLogs('latter')">HA logs (latter)</button>
              <button type="button" class="btn btn-secondary btn-compact" id="btn-native-dev-logs" onclick="openNativeHaLogs(STATE?.config?.device_slug || 'esphome')">HA logs (Device)</button>
              <button type="button" class="btn btn-secondary btn-compact" onclick="openNativeHaLogs('esphome')">HA logs (esphome)</button>
              <button type="button" class="btn btn-secondary btn-compact" onclick="openNativeHaIntegrations()">Latter integration</button>
            </div>
            <div class="input-action-row">
              <select id="log-filter-select" aria-label="Log filter" onchange="renderLogsView()">
                <option value="all">All Latter &amp; ESPHome entries</option>
                <option value="device">Selected Device only</option>
                <option value="latter">Latter only</option>
                <option value="errors">Warnings &amp; errors only</option>
              </select>
              <button type="button" class="btn btn-text btn-compact" onclick="refreshState(false)">Refresh</button>
              <button type="button" class="btn btn-text btn-compact" onclick="copyTextById('internal-log-output')">Copy</button>
              <button type="button" class="btn btn-danger btn-compact" onclick="clearInternalLogs()">Clear</button>
            </div>
            <pre id="internal-log-output" class="log-output mono">No events logged yet.</pre>
          </div>
        </details>
      </section>

      <!-- DEVICES: LANDING -->
      <section id="view-select_device_prompt">
        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">All Devices</h3>
              <p class="card-description">Open a Device to manage it. Add display opens Latter in Home Assistant, where you choose Add Device. BLE phones, watches and tags are added here.</p>
            </div>
            <div class="card-header-actions">
              <select id="device-category-filter" aria-label="Device category" onchange="onFilterDeviceCategory(this.value)"></select>
              <button type="button" class="btn btn-secondary" onclick="openHaPage('/config/integrations/integration/latter')">Add display</button>
              <button type="button" class="btn btn-primary" onclick="openAddDeviceModal()">Add BLE Device</button>
            </div>
          </div>
          <div class="card-content"><div id="prompt-devices-list"></div></div>
        </div>
      </section>

      <!-- DEVICE: OVERVIEW -->
      <section id="view-dashboard" class="hidden">
        <div id="dash-health" class="hidden"></div>
        <div class="stat-grid">
          <div class="stat"><span>Battery</span><strong id="st-battery">—</strong></div>
          <div class="stat"><span>Wi-Fi signal</span><strong id="st-wifi">—</strong></div>
          <div class="stat"><span>Firmware</span><strong id="st-fw-version">—</strong></div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Now</h3>
              <p class="card-description">Where this Device is and what it's playing.</p>
            </div></div>
            <div class="card-content kv-list">
              <div class="kv-row"><span id="st-area-label">Area</span><strong id="st-area">—</strong></div>
              <div class="kv-row"><span>Speaker</span><strong id="now-speaker">—</strong></div>
              <div class="kv-row"><span>Now playing</span><strong id="now-playing">—</strong></div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading"><h3 class="card-title">Device status</h3></div></div>
            <div class="card-content kv-list">
              <div class="kv-row"><span>Hardware model</span><strong id="dash-hw-model">—</strong></div>
              <div class="kv-row"><span>IP address</span><strong id="dash-ip-addr">—</strong></div>
              <div class="kv-row"><span>Location mode</span><strong id="dash-ble-mode">—</strong></div>
              <div class="kv-row" id="dash-row-ble-proxy"><span>Nearest BLE proxy</span><strong id="dash-ble-proxy">—</strong></div>
              <div class="kv-row"><span>Device group</span><strong id="st-group">—</strong></div>
            </div>
            <div class="card-actions">
              <button type="button" class="btn btn-text" onclick="navigateToView('system')">Device settings</button>
              <button type="button" class="btn btn-secondary" onclick="exportBackupToComputer('device')">Download backup</button>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Quick actions</h3>
            <p class="card-description">Run a Device action, or apply a saved configuration profile.</p>
          </div></div>
          <div class="card-content">
            <div id="dash-quick-actions" class="input-action-row"></div>
            <div class="settings-list">
              <div class="settings-row hidden" id="dash-power-profile-wrap"><div class="settings-row-text"><label class="row-label" for="dash-power-profile-select">Sleep &amp; wake power profile</label></div><div class="settings-row-control"><select id="dash-power-profile-select" onchange="if (this.dataset.ent) espSelect(this.dataset.ent, this.value)"></select></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="quick-profile-select">Configuration profile</label></div><div class="settings-row-control"><select id="quick-profile-select"></select><button type="button" class="btn btn-secondary" onclick="applyQuickProfileFromOverview()">Apply</button></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-assigned_person">Assigned person</label><p class="row-description">Creates <code>sensor.&lt;person&gt;_current_area</code>.</p></div><div class="settings-row-control"><select id="cfg-assigned_person" onchange="onAssignedPersonChanged(this.value)"></select></div></div>
            </div>
          </div>
        </div>
        <div class="card hidden" id="dash-sensor-entities-card">
          <div class="card-header"><div class="card-heading">
            <h3 class="card-title">Device sensors &amp; controls</h3>
            <p class="card-description">Other sensors, switches and settings this ESPHome device exposes.</p>
          </div></div>
          <div class="card-content"><div id="dash-device-entities" class="settings-list"></div></div>
        </div>
      </section>

      <!-- DEVICE: DISPLAY & HOME -->
      <section id="view-home_display" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Display &amp; appearance</h3>
              <p class="card-description">Brightness, auto-brightness schedule, clock face, and color profile.</p>
            </div></div>
            <div class="card-content">
              <div id="embedded-display" class="settings-list"></div>
              <div class="settings-list">
                <div class="settings-row">
                  <div class="settings-row-text"><label class="row-label" for="dev-custom-palette-select">Custom color</label><p class="row-description">Used when the color profile is Custom.</p></div>
                  <div class="settings-row-control">
                    <span id="dev-color-swatch" class="swatch" aria-hidden="true"></span>
                    <select id="dev-custom-palette-select" onchange="onSelectDeviceCustomPalette(this.value)"></select>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Home screen &amp; Area UI</h3>
              <p class="card-description">Home screen behavior, dock apps, and the default Area Control category.</p>
            </div></div>
            <div class="card-content">
              <div id="embedded-home" class="settings-list"></div>
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-default_page_size">Area cards per page</label></div><div class="settings-row-control"><input type="number" id="cfg-default_page_size" min="1" max="20" value="3" onchange="saveField('device', this)" onkeydown="if (event.key === 'Enter') this.blur()"></div></div>
              </div>
              <div class="settings-row stacked">
                <div class="settings-row-text"><span class="row-label">Home dock apps</span><p class="row-description">Select an app to show or hide it, and use the arrows to reorder. Changes apply when you save.</p></div>
                <div class="settings-row-control"><div id="dock-pills-container" class="pill-list"></div></div>
                <input type="hidden" id="cfg-dock_apps">
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Wallpapers</h3>
              <p class="card-description">Choose a built-in preset, upload a photo, or star several favorites to rotate.</p>
            </div>
            <div class="card-header-actions">
              <select id="cfg-wallpaper_cycle_minutes" aria-label="Favorite rotation" onchange="saveField('device', this)">
                <option value="0">Rotation: off</option>
                <option value="15">Rotate every 15 min</option>
                <option value="60">Rotate every hour</option>
                <option value="360">Rotate every 6 h</option>
                <option value="1440">Rotate daily</option>
              </select>
              <button type="button" class="btn btn-secondary btn-compact" onclick="selectWallpaperSource('')">Turn off wallpaper</button>
            </div>
          </div>
          <div class="card-content">
            <div class="input-action-row">
              <input type="file" id="wp-file-input" accept="image/*" aria-label="Wallpaper image">
              <button type="button" class="btn btn-primary" onclick="uploadWallpaperFile()">Upload photo</button>
            </div>
            <div id="wp-gallery-grid" class="wp-gallery"></div>
          </div>
        </div>
      </section>

      <!-- DEVICE: AUDIO & VOICE -->
      <section id="view-audio_voice" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Voice assistant &amp; wake word</h3>
              <p class="card-description">Wake word mode, active wake word, and visual profile.</p>
            </div></div>
            <div class="card-content">
              <div id="embedded-voice-primary" class="settings-list"></div>
              <div class="settings-list">
                <div class="settings-row" id="row-sync-device-area">
                  <div class="settings-row-text"><label class="row-label" for="cfg-sync_device_area">Voice Follows Me</label><p class="row-description">Moves this Device's Home Assistant Area with it, so voice commands act on the Area it's in.</p></div>
                  <div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="cfg-sync_device_area" onchange="saveField('device', this)"></div>
                </div>
                <div class="settings-row" id="row-area-follow-dwell">
                  <div class="settings-row-text"><label class="row-label" for="cfg-area_follow_dwell_s">Voice Follows Me delay</label><p class="row-description">How long Bluetooth must place the Device in a new Area before it moves there. Picking an Area on the Device moves it at once.</p></div>
                  <div class="settings-row-control"><input type="range" id="cfg-area_follow_dwell_s" min="3" max="60" step="1" value="10" oninput="renderDwellValue()" onchange="saveField('device', this)"><span class="chip" id="dwell-value">—</span></div>
                </div>
              </div>
              <details class="sub-collapsible" id="details-voice-sens">
                <summary>Wake word sensitivity (per model)</summary>
                <div class="card-content"><div id="embedded-voice-sens" class="settings-list"></div></div>
              </details>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Sound &amp; media player</h3>
              <p class="card-description">Alert volume, volume step, player appearance, and speakers.</p>
            </div></div>
            <div class="card-content">
              <div id="embedded-sound" class="settings-list"></div>
              <div id="embedded-music" class="settings-list"></div>
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-default_speaker">Default speaker</label></div><div class="settings-row-control"><select id="cfg-default_speaker" onchange="saveField('device', this)"></select></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-ma_player_entity">Music Assistant player</label><p class="row-description">This Device's own player in Music Assistant, needed for library playback, queues and lyrics.</p></div><div class="settings-row-control"><select id="cfg-ma_player_entity" onchange="saveField('device', this)"></select></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-area_handoff">Media follows this Device to its new Area</label><p class="row-description">When Bluetooth moves this Device to another Area, or you pick one on it, its speaker switches to that Area's speaker and playing music moves along.</p></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="cfg-area_handoff" onchange="saveField('device', this)"></div></div>
              </div>
              <details class="sub-collapsible">
                <summary>Library sorting</summary>
                <div class="card-content"><div id="embedded-music-sort" class="settings-list"></div></div>
              </details>
            </div>
          </div>
        </div>
      </section>

      <!-- DEVICE: POWER & BATTERY -->
      <section id="view-power" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Sleep &amp; wake</h3>
              <p class="card-description">Screen timeouts, pickup and tap to wake, docked screensaver, and hibernate.</p>
            </div></div>
            <div class="card-content"><div id="embedded-sleep" class="settings-list"></div></div>
          </div>
          <div class="card">
            <div class="card-header"><div class="card-heading">
              <h3 class="card-title">Battery &amp; power</h3>
              <p class="card-description">Live battery level, charging, voltage, and temperature.</p>
            </div></div>
            <div class="card-content"><div id="embedded-battery" class="settings-list"></div></div>
          </div>
        </div>
      </section>

      <!-- DEVICE: DEVICE SETTINGS -->
      <section id="view-system" class="hidden">
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><div class="card-heading"><h3 class="card-title">Device</h3></div></div>
            <div class="card-content settings-list">
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-device_slug">ESPHome node name</label><p class="row-description">Set when the Device was added; entities are <code>sensor.&lt;name&gt;_*</code>.</p></div><div class="settings-row-control"><input type="text" id="cfg-device_slug" readonly></div></div>
              <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-device_group">Device group</label></div><div class="settings-row-control"><select id="cfg-device_group" onchange="saveField('device', this)"></select></div></div>
            </div>
          </div>

          <div class="card">
            <div class="card-header"><div class="card-heading"><h3 class="card-title">Location &amp; BLE</h3></div></div>
            <div class="card-content">
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-native_ble_tracking">Track the Area with BLE proxies</label></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="cfg-native_ble_tracking" onchange="saveField('device', this)"></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-ble_auto_switch">Switch the active Area on movement</label></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="cfg-ble_auto_switch" onchange="saveField('device', this)"></div></div>
              </div>
              <div id="embedded-area-ble" class="settings-list"></div>
              <div class="settings-list">
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-default_area">Fallback Area</label></div><div class="settings-row-control"><select id="cfg-default_area" onchange="saveField('device', this)"></select></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-ble_target_address">BLE target</label><p class="row-description">Optional MAC address or <code>private_ble_device</code> entity.</p></div><div class="settings-row-control"><input type="text" id="cfg-ble_target_address" class="mono" placeholder="Auto-discovered" onchange="saveField('device', this)" onkeydown="if (event.key === 'Enter') this.blur()"></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-ble_beacon_uuid">iBeacon UUID</label></div><div class="settings-row-control"><input type="text" id="cfg-ble_beacon_uuid" class="mono" onchange="saveField('device', this)" onkeydown="if (event.key === 'Enter') this.blur()"></div></div>
                <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="cfg-presence_entity">External Area sensor</label><p class="row-description">Optional; for example a Bermuda Area sensor.</p></div><div class="settings-row-control"><select id="cfg-presence_entity" onchange="saveField('device', this)"></select></div></div>
              </div>
            </div>
          </div>
        </div>

        <div class="card" id="card-device-ha">
          <div class="card-header"><div class="card-heading"><h3 class="card-title">In Home Assistant</h3></div></div>
          <div class="card-content settings-list">
            <div class="settings-row" id="row-open-in-ha">
              <div class="settings-row-text"><span class="row-label">Device page</span><p class="row-description">Every entity of the ESPHome device, its logs and its firmware update.</p></div>
              <div class="settings-row-control"><button type="button" class="btn btn-secondary btn-compact" onclick="openDeviceInHa()">Open in Home Assistant</button></div>
            </div>
            <div class="settings-row" id="row-diagnostics">
              <div class="settings-row-text"><span class="row-label">Diagnostics</span><p class="row-description">A JSON file for troubleshooting, with private values redacted.</p></div>
              <div class="settings-row-control"><button type="button" class="btn btn-secondary btn-compact" onclick="downloadDeviceDiagnostics()">Download diagnostics</button></div>
            </div>
            <div class="settings-row" id="row-replace-hardware">
              <div class="settings-row-text"><span class="row-label">Replace hardware</span><p class="row-description">Opens Latter in Home Assistant. On this Device, choose Reconfigure or Replace Hardware; its settings move to the new hardware.</p></div>
              <div class="settings-row-control"><button type="button" class="btn btn-secondary btn-compact" onclick="openHaPage('/config/integrations/integration/latter')">Open Latter</button></div>
            </div>
          </div>
        </div>

        <details class="card">
          <summary class="card-header"><div class="card-heading"><h3 class="card-title">Diagnostics</h3></div></summary>
          <div class="card-content">
            <div id="embedded-network" class="settings-list"></div>
            <details class="sub-collapsible" id="details-developer">
              <summary>Developer</summary>
              <div class="card-content"><div id="embedded-developer" class="settings-list"></div></div>
            </details>
            <details class="sub-collapsible">
              <summary>All entities</summary>
              <div class="card-content">
                <input type="text" id="esp-search" placeholder="Filter by name or entity ID" aria-label="Filter entities" oninput="renderRawEntityList()">
                <div id="raw-entity-items" class="settings-list"></div>
              </div>
            </details>
          </div>
        </details>

        <div class="card danger">
          <div class="card-header"><div class="card-heading"><h3 class="card-title">Danger Zone</h3></div></div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text"><span class="row-label">Reset to defaults</span><p class="row-description">Erases the settings saved on the Device, resets its Latter options, or both. Wi-Fi and pairing are kept.</p></div>
              <div class="settings-row-control"><button type="button" class="btn btn-secondary btn-compact" onclick="openResetDeviceModal()">Reset…</button></div>
            </div>
            <div class="settings-row">
              <div class="settings-row-text"><span class="row-label">Remove Device</span><p class="row-description">Removes it from Latter. The ESPHome device stays in Home Assistant and can be added again.</p></div>
              <div class="settings-row-control"><button type="button" class="btn btn-danger btn-compact" onclick="removeManagedDevice(STATE.subentry_id, STATE.title)">Remove…</button></div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</div>

<dialog id="latter-rm-modal" class="studio-dialog" aria-labelledby="latter-rm-title">
  <div class="dialog-body">
    <h3 class="dialog-title danger" id="latter-rm-title">Remove Device from Latter?</h3>
    <p class="dialog-text" id="latter-rm-desc">Your ESPHome device stays in Home Assistant.</p>
    <div class="dialog-actions">
      <button type="button" class="btn btn-secondary" onclick="closeRemoveDeviceModal()">Cancel</button>
      <button type="button" class="btn btn-danger-filled" onclick="confirmRemoveManagedDevice()">Remove Device</button>
    </div>
  </div>
</dialog>

<dialog id="latter-reset-modal" class="studio-dialog" aria-labelledby="latter-reset-title">
  <div class="dialog-body">
    <h3 class="dialog-title danger" id="latter-reset-title">Reset to defaults?</h3>
    <div class="settings-list">
      <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="latter-reset-device-settings">Device settings</label><p class="row-description">Erases everything saved on the Device; it restarts.</p></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="latter-reset-device-settings" checked onchange="updateResetDeviceConfirm()"></div></div>
      <div class="settings-row"><div class="settings-row-text"><label class="row-label" for="latter-reset-latter-options">Latter options for this Device</label></div><div class="settings-row-control"><input type="checkbox" class="switch" role="switch" id="latter-reset-latter-options" checked onchange="updateResetDeviceConfirm()"></div></div>
    </div>
    <p class="dialog-text">Wi-Fi and pairing are kept, so the Device rejoins Home Assistant by itself. Its ESPHome binding and Music Assistant player link are kept too.</p>
    <div class="dialog-actions">
      <button type="button" class="btn btn-secondary" onclick="closeResetDeviceModal()">Cancel</button>
      <button type="button" class="btn btn-danger-filled" id="latter-reset-confirm-btn" onclick="confirmResetDevice()">Reset</button>
    </div>
  </div>
</dialog>

<dialog id="latter-add-dev-modal" class="studio-dialog" aria-labelledby="latter-add-dev-title">
  <div class="dialog-body">
    <h3 class="dialog-title" id="latter-add-dev-title">Add a BLE phone, watch or tag</h3>
    <p class="dialog-text">Latter displays are added through Home Assistant's ESPHome discovery.</p>
    <div class="stacked-field"><label for="ble-candidate-picker">Discovered Bluetooth devices</label><select id="ble-candidate-picker" onchange="onSelectBleCandidate(this.value)"></select></div>
    <div class="stacked-field"><label for="ble-custom-name">Name</label><input type="text" id="ble-custom-name" placeholder="e.g. phone, watch, keys"></div>
    <div class="stacked-field"><label for="ble-custom-addr">MAC address, <code>private_ble_device</code> entity, or iBeacon UUID</label><input type="text" id="ble-custom-addr" class="mono" placeholder="AA:BB:CC:DD:EE:FF"></div>
    <div class="stacked-field"><label for="ble-custom-person">Assigned person (optional)</label><select id="ble-custom-person"></select></div>
    <div class="dialog-actions">
      <button type="button" class="btn btn-secondary" onclick="closeAddDeviceModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="confirmAddDeviceModal()">Add Device</button>
    </div>
  </div>
</dialog>

<dialog id="latter-cw-modal" class="studio-dialog" aria-labelledby="latter-cw-title">
  <div class="dialog-body">
    <h3 class="dialog-title" id="latter-cw-title">Add a custom color</h3>
    <p class="dialog-text">Pick a color and save it to the System color library.</p>
    <div class="color-wheel"><canvas id="latter-cw-canvas" width="220" height="220" aria-label="Color wheel"></canvas></div>
    <div class="color-hex-row">
      <span id="latter-cw-preview" class="swatch" aria-hidden="true"></span>
      <input type="text" id="latter-cw-hex" aria-label="Hex color" oninput="onCwHexInput(this.value)">
    </div>
    <div class="stacked-field"><label for="latter-cw-name">Name</label><input type="text" id="latter-cw-name" placeholder="e.g. Sunset Coral"></div>
    <div class="dialog-actions">
      <button type="button" class="btn btn-secondary" onclick="closeColorWheelModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="saveColorWheelSelection()">Save color</button>
    </div>
  </div>
</dialog>

<div id="toast" class="toast hidden" role="status" aria-live="polite"></div>
</div>`;

let HASS_REF = null;
let SHADOW_ROOT = null;
let HOST_ELEMENT = null;
let ACTIVE_SUBENTRY_ID = "";
let WS_UNSUB = null;
let SUB_GEN = 0;

function getStudioActiveElement() {
  if (SHADOW_ROOT && SHADOW_ROOT.activeElement) {
    return SHADOW_ROOT.activeElement;
  }
  return window.document ? window.document.activeElement : null;
}

const doc = {
  getElementById: (id) => SHADOW_ROOT ? SHADOW_ROOT.getElementById(id) : null,
  querySelector: (sel) => SHADOW_ROOT ? SHADOW_ROOT.querySelector(sel) : null,
  querySelectorAll: (sel) => SHADOW_ROOT ? SHADOW_ROOT.querySelectorAll(sel) : [],
  createElement: (tag) => window.document.createElement(tag),
  body: {
    appendChild: (el) => {
      if (el && el.tagName === "A") {
        window.document.body.appendChild(el);
      } else if (SHADOW_ROOT) {
        const root = SHADOW_ROOT.querySelector(".studio-root") || SHADOW_ROOT;
        root.appendChild(el);
      }
    },
    removeChild: (el) => {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }
  }
};

const esc = (s) => String(s ?? "").replace(/[&<>"'`]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;","`":"&#96;"}[c]));
const jsArg = (v) => esc(JSON.stringify(v));

// Locale-aware formatting (docs/studio-design.md section 6): the user's Home Assistant language,
// time zone setting and unit system.
function studioLocale() {
  return HASS_REF?.locale?.language || HASS_REF?.language || undefined;
}

function fmtNumber(value, digits = 0) {
  const n = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat(studioLocale(), {maximumFractionDigits: digits}).format(n);
}

function fmtPercent(value) {
  const n = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat(studioLocale(), {style: "percent", maximumFractionDigits: 0}).format(n / 100);
}

function fmtDistance(meters) {
  const m = Number(meters);
  if (meters === null || meters === undefined || meters === "" || !Number.isFinite(m)) return "";
  return HASS_REF?.config?.unit_system?.length === "mi"
    ? `${fmtNumber(m * 3.28084, 1)} ft`
    : `${fmtNumber(m, 1)} m`;
}

function fmtAgo(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s)) return "—";
  const rtf = new Intl.RelativeTimeFormat(studioLocale(), {numeric: "auto"});
  if (s < 60) return rtf.format(-Math.round(s), "second");
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  return rtf.format(-Math.round(s / 3600), "hour");
}

function fmtDateTime(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return iso || "—";
  const opts = {dateStyle: "short", timeStyle: "medium"};
  if (HASS_REF?.locale?.time_zone === "server" && HASS_REF?.config?.time_zone) opts.timeZone = HASS_REF.config.time_zone;
  try {
    return d.toLocaleString(studioLocale(), opts);
  } catch (_e) {
    return d.toLocaleString();
  }
}

// Shared markup (docs/studio-design.md section 4). Labels and descriptions are passed already escaped.
const ICON_DELETE = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 4h-3.5l-1-1h-5l-1 1H5v2h14M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12Z"/></svg>`;

function settingsRowHtml(labelHtml, descriptionHtml, controlHtml) {
  return `<div class="settings-row">
    <div class="settings-row-text"><span class="row-label">${labelHtml}</span>${descriptionHtml ? `<p class="row-description">${descriptionHtml}</p>` : ""}</div>
    <div class="settings-row-control">${controlHtml || ""}</div>
  </div>`;
}

function emptyStateHtml(text) {
  return `<div class="empty-state">${esc(text)}</div>`;
}

function iconButtonHtml(icon, label, onclick, variant = "") {
  return `<button type="button" class="btn-icon ${variant}" aria-label="${esc(label)}" title="${esc(label)}" onclick="${onclick}">${icon}</button>`;
}

function cssColorToHex(color) {
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.fillStyle = String(color || "").trim() || ctx.fillStyle;
  return String(ctx.fillStyle).toUpperCase();
}

// Native <dialog>: Esc closes it, focus moves into it on open and returns to the opener on close.
let DIALOG_RETURN_FOCUS = null;

function openDialog(id) {
  const dlg = doc.getElementById(id);
  if (!dlg || dlg.open) return;
  DIALOG_RETURN_FOCUS = getStudioActiveElement();
  dlg.showModal();
}

function closeDialog(id) {
  const dlg = doc.getElementById(id);
  if (dlg && dlg.open) dlg.close();
}

function bindDialogs() {
  doc.querySelectorAll("dialog.studio-dialog").forEach(dlg => dlg.addEventListener("close", () => {
    const el = DIALOG_RETURN_FOCUS;
    DIALOG_RETURN_FOCUS = null;
    if (el && typeof el.focus === "function") el.focus();
  }));
}
let STATE = null;
let CALENDARS = [];
// D-010: every setting applies as soon as it changes. Changes are coalesced per scope and sent as one
// partial save of just the changed keys; a failure shows the error toast and reverts the form.
const PENDING_KEYS = {system: new Set(), device: new Set()};
const SAVE_TIMERS = {system: null, device: null};
const SAVE_IN_FLIGHT = {system: false, device: false};
let INITIAL_FORM_LOADED = false;

let CURRENT_SCOPE = "device";
let DEVICE_SELECTED = false;
let POLL_TIMER = null;
let SELECTED_SURVEY_ID = localStorage.getItem("latter_ble_survey_subentry") || "";
let PREVIEW_CAMERA_ENTITY = "";
let DEVICE_SORT_COL = "title";
let DEVICE_SORT_ASC = true;
let DEVICE_CATEGORY_FILTER = "all";

const SYSTEM_VIEWS = [
  "system_overview",
  "shared_entities",
  "remotes",
  "system_sync",
  "area_tracking",
  "system_admin"
];

const DEVICE_VIEWS = [
  "select_device_prompt",
  "dashboard",
  "home_display",
  "audio_voice",
  "power",
  "system"
];

const ALL_VIEWS = SYSTEM_VIEWS.concat(DEVICE_VIEWS);

const DOCK_APP_META = [
  {token: "music",  label: "Music"},
  {token: "alarm",  label: "Home Hub"},
  {token: "area",   label: "Area"},
  {token: "remote", label: "Remote"},
  {token: "camera", label: "Cameras"},
  {token: "games",  label: "Games"},
  {token: "tools",  label: "Tools"}
];

// Must match custom_components/latter/studio/scope.py (checked by tests/test_protocol.py).
// System commands never act on the selected Device; one that acts on a Device names it in its payload.
const SYSTEM_WS_COMMANDS = new Set([
  "set_ble_area_offset",
  "set_area_fusion",
  "auto_calibrate_here",
  "system_entity_action",
  "send_announcement",
  "check_system_updates",
  "clear_internal_logs",
  "remove_device",
  "add_ble_device",
  "set_device_remote_group",
  "create_device_group",
  "delete_device_group",
  "capture_profile",
  "delete_profile",
  "apply_profile",
  "test_doorbell_speaker",
  "save_system_config"
]);

// Device commands act on the selected Device (ACTIVE_SUBENTRY_ID).
const DEVICE_WS_COMMANDS = new Set([
  "esphome_entity_action",
  "upload_wallpaper",
  "select_wallpaper",
  "toggle_wallpaper_favorite",
  "delete_wallpaper",
  "save_device_config"
]);

const STUDIO_REV = 3;

// Every Studio websocket call goes through here: a failure shows an error toast and resolves to null.
async function callStudioWS(msg) {
  if (!HASS_REF) {
    showToast("Home Assistant connection not ready", "error");
    return null;
  }
  try {
    return await HASS_REF.callWS(msg);
  } catch (err) {
    showToast(`Failed: ${err?.message || err?.code || err || "unknown error"}`, "error");
    return null;
  }
}

async function callStudioCommand(bodyObj) {
  const { command, ...payload } = bodyObj || {};
  const isDevice = DEVICE_WS_COMMANDS.has(command);
  if (!isDevice && !SYSTEM_WS_COMMANDS.has(command)) {
    showToast(`Failed: unknown Studio command '${command}'`, "error");
    return null;
  }
  if (isDevice && !ACTIVE_SUBENTRY_ID) {
    showToast("Failed: select a Device first", "error");
    return null;
  }
  const msg = {
    type: isDevice ? "latter/device/command" : "latter/system/command",
    command,
    payload
  };
  if (ACTIVE_SUBENTRY_ID) msg.subentry_id = ACTIVE_SUBENTRY_ID;
  return await callStudioWS(msg);
}

function toggleParentHaSidebar() {
  if (HOST_ELEMENT) {
    HOST_ELEMENT.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }
}

function closeCameraPreviewBox() {
  doc.getElementById("cam-preview-box")?.classList.add("hidden");
}

let TOAST_TIMER = null;

function showToast(msg, kind = "info") {
  const t = doc.getElementById("toast");
  if (!t) return;
  const isError = kind === "error";
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.setAttribute("role", isError ? "alert" : "status");
  t.classList.remove("hidden");
  if (TOAST_TIMER) clearTimeout(TOAST_TIMER);
  TOAST_TIMER = setTimeout(() => t.classList.add("hidden"), isError ? 6000 : 2400);
}

function renderLogsView() {
  const logPre = doc.getElementById("internal-log-output");
  if (!logPre) return;
  const allLogs = STATE?.internal_logs || [];
  const filterMode = doc.getElementById("log-filter-select")?.value || "all";
  const slug = (STATE?.config?.device_slug || "").toLowerCase();
  const slugHyphen = slug.replace(/_/g, "-");

  const devBtn = doc.getElementById("btn-native-dev-logs");
  if (devBtn && slug) {
    devBtn.textContent = `HA logs (${slug})`;
  }

  const filtered = allLogs.filter(l => {
    const hay = `${l.source || ''} ${l.message || ''}`.toLowerCase();
    if (filterMode === "device" && slug) {
      return hay.includes(slug) || hay.includes(slugHyphen);
    }
    if (filterMode === "latter") {
      return hay.includes("latter") || !(l.source || "").startsWith("ha:");
    }
    if (filterMode === "errors") {
      return ["WARN", "WARNING", "ERROR", "CRITICAL"].includes((l.level || "").toUpperCase());
    }
    return true;
  });

  logPre.textContent = filtered.length
    ? filtered.map(l => `[${fmtDateTime(l.ts)}] [${l.level}] (${l.source}) ${l.message}`).join("\n\n")
    : "No matching log entries.";
}

// Home Assistant's own pages open in the same tab, the way HA's panels navigate (history API +
// location-changed); Back returns to Studio.
function openHaPage(path) {
  try {
    window.history.pushState(null, "", path);
  } catch (_e) {
    window.location.assign(path);
    return;
  }
  window.dispatchEvent(new CustomEvent("location-changed", {detail: {replace: false}}));
}

function openNativeHaLogs(filterTerm) {
  openHaPage(`/config/logs${filterTerm ? `?filter=${encodeURIComponent(filterTerm)}` : ""}`);
}

function openNativeHaIntegrations() {
  openHaPage("/config/integrations/integration/latter");
}

function openDeviceInHa() {
  const devId = STATE?.links?.esphome_device_id;
  if (!devId) {
    showToast("This Device has no ESPHome device in Home Assistant", "error");
    return;
  }
  openHaPage(`/config/devices/device/${encodeURIComponent(devId)}`);
}

// Device diagnostics come from Home Assistant's diagnostics API, opened through a short-lived signed path.
async function downloadDeviceDiagnostics() {
  const links = STATE?.links || {};
  if (!links.entry_id || !links.latter_device_id) {
    showToast("Diagnostics aren't available until the Device is set up", "error");
    return;
  }
  const signed = await callStudioWS({
    type: "auth/sign_path",
    path: `/api/diagnostics/config_entry/${links.entry_id}/device/${links.latter_device_id}`,
    expires: 60
  });
  if (!signed?.path) return;
  const a = document.createElement("a");
  a.href = signed.path;
  a.download = "";
  a.classList.add("offscreen");
  SHADOW_ROOT.appendChild(a);
  a.click();
  a.remove();
}

// Messages for Latter's repairs (kind = the repair's translation key in strings.json).
const ISSUE_TEXT = {
  link_ma_player: () => "Not linked to its Music Assistant player.",
  missing_mapped_entity: (i) => `A chosen entity no longer exists${i.detail ? `: ${i.detail}` : ""}.`,
  ble_no_proxies: () => "BLE Area tracking is on, but no Bluetooth proxy is assigned to an Area.",
  slot_push_failing: () => "Latter can't send Area and browse pages to this Device.",
  device_crashed: (i) => (i.detail === "stall"
    ? "Restarted itself after its main loop stalled for 30 seconds."
    : `Restarted after a crash${i.detail ? ` (${i.detail})` : ""}.`),
  device_brownout: () => "Restarted after a power dip (brownout).",
  firmware_rolled_back: () => "A firmware update failed to start; the previous firmware is running."
};

function issueMessage(issue) {
  const fn = ISSUE_TEXT[issue.kind];
  return fn ? fn(issue) : `Repair: ${issue.kind.replace(/_/g, " ")}.`;
}

function renderDeviceHealth() {
  const box = doc.getElementById("dash-health");
  if (!box) return;
  const issues = (STATE?.issues || []).filter(i => i.subentry_id && i.subentry_id === STATE?.subentry_id);
  if (!issues.length) {
    box.className = "hidden";
    box.innerHTML = "";
    return;
  }
  const isError = issues.some(i => i.severity === "error" || i.severity === "critical");
  box.className = `alert ${isError ? "alert-error" : "alert-warning"}`;
  box.setAttribute("role", "alert");
  box.innerHTML = `<div class="alert-body"><strong>Needs attention</strong>
      <ul class="alert-list">${issues.map(i => `<li>${esc(issueMessage(i))}</li>`).join("")}</ul></div>
    <button type="button" class="btn btn-secondary btn-compact" onclick="openHaPage('/config/repairs')">Open Repairs</button>`;
}

function renderSystemIssues() {
  const box = doc.getElementById("sys-issues-list");
  if (!box) return;
  const issues = STATE?.issues || [];
  box.innerHTML = issues.length
    ? issues.map(i => {
        const sev = (i.severity === "error" || i.severity === "critical") ? "chip-error" : "chip-warning";
        const open = i.subentry_id
          ? `<button type="button" class="btn btn-text btn-compact" onclick="switchSystemDevice(${jsArg(i.subentry_id)})">Open Device</button>`
          : "";
        return settingsRowHtml(
          `${esc(i.device_title || "Latter")} <span class="chip ${sev}">${i.severity === "warning" ? "Warning" : "Error"}</span>`,
          esc(issueMessage(i)),
          open
        );
      }).join("")
    : emptyStateHtml("No issues.");
}

async function clearInternalLogs() {
  const data = await callStudioCommand({command: "clear_internal_logs"});
  if (data) {
    applyStateToDom(data, false);
    showToast("Cleared studio events");
  }
}

function saveSetting(scope, key, delayMs = 250) {
  PENDING_KEYS[scope].add(key);
  clearTimeout(SAVE_TIMERS[scope]);
  SAVE_TIMERS[scope] = setTimeout(() => flushSettings(scope), delayMs);
}

// A cfg-<key> control saves its own key.
function saveField(scope, el) {
  saveSetting(scope, String(el?.id || "").replace(/^cfg-/, ""));
}

async function flushSettings(scope) {
  clearTimeout(SAVE_TIMERS[scope]);
  SAVE_TIMERS[scope] = null;
  if (SAVE_IN_FLIGHT[scope] || !PENDING_KEYS[scope].size) return;
  const keys = [...PENDING_KEYS[scope]];
  PENDING_KEYS[scope].clear();
  const all = scope === "system" ? collectSystemSettings() : collectDeviceSettings();
  const config = {};
  keys.forEach(k => { if (k in all) config[k] = all[k]; });
  SAVE_IN_FLIGHT[scope] = true;
  const data = await callStudioCommand({command: scope === "system" ? "save_system_config" : "save_device_config", config});
  SAVE_IN_FLIGHT[scope] = false;
  // On failure the error toast is already showing; put the form back to the last saved state.
  applyStateToDom(data || STATE, {[scope]: canReloadForm(scope)});
  if (PENDING_KEYS[scope].size) flushSettings(scope);
}

// A form follows live state unless the user is in the middle of an edit there (a focused control, a pending
// save, or a list row that has been added but not filled in yet).
function canReloadForm(scope) {
  if (PENDING_KEYS[scope].size || SAVE_TIMERS[scope] || SAVE_IN_FLIGHT[scope]) return false;
  if (scope === "system" && [...doc.querySelectorAll(
    "#cameras-list select, #calendars-list select, #remotes-list select, #volume-overrides-list select"
  )].some(sel => !sel.value)) return false;
  const el = getStudioActiveElement();
  return !(el && ["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName));
}


const VIEW_TITLES = {
  system_overview: "System overview",
  shared_entities: "Shared entities",
  remotes: "Media & remotes",
  system_sync: "Groups & profiles",
  area_tracking: "BLE & Area presence",
  system_admin: "System settings",
  select_device_prompt: "Devices",
  dashboard: "Overview",
  home_display: "Display & home",
  audio_voice: "Audio & voice",
  power: "Power & battery",
  system: "Device settings"
};
let CURRENT_VIEW_ID = "select_device_prompt";

function updateUnifiedPageTitle(viewId) {
  if (viewId) CURRENT_VIEW_ID = viewId;
  const titleEl = doc.getElementById("unified-page-title");
  if (!titleEl) return;
  const baseTitle = VIEW_TITLES[CURRENT_VIEW_ID] || "Devices";
  if (CURRENT_SCOPE === "device" && DEVICE_SELECTED && CURRENT_VIEW_ID !== "select_device_prompt") {
    const devTitle = STATE?.esphome?.device?.name || STATE?.title || "";
    titleEl.innerHTML = `<span>${esc(baseTitle)}</span>${devTitle ? `<span class="page-subtitle">${esc(devTitle)}</span>` : ""}`;
  } else {
    titleEl.textContent = baseTitle;
  }
}

function updateTopHeaderForScope() {
  const isHH = (CURRENT_SCOPE === "system") || !DEVICE_SELECTED;
  const devTitle = STATE?.esphome?.device?.name || STATE?.title || "Device";
  const devNavLbl = doc.getElementById("nav-selected-device-label");
  if (devNavLbl) devNavLbl.textContent = devTitle;

  const updPill = doc.getElementById("hdr-update-pill");
  if (updPill) {
    const showUpd = !isHH && !!(STATE?.live?.fw_update_available && STATE?.live?.fw_update_entity);
    updPill.classList.toggle("hidden", !showUpd);
    if (showUpd) {
      const lat = STATE?.live?.fw_latest_version ? ` (v${String(STATE.live.fw_latest_version).replace(/^v/i, "")})` : "";
      updPill.textContent = `Install update${lat}`;
    }
  }
  doc.getElementById("nav-scope-system").classList.toggle("hidden", CURRENT_SCOPE !== "system");
  doc.getElementById("nav-scope-devices-list")?.classList.toggle("hidden", CURRENT_SCOPE !== "device" || DEVICE_SELECTED);
  doc.getElementById("nav-scope-device").classList.toggle("hidden", CURRENT_SCOPE !== "device" || !DEVICE_SELECTED);
  updateUnifiedPageTitle(CURRENT_VIEW_ID);
}

async function triggerHeaderFirmwareUpdate() {
  const entId = STATE?.live?.fw_update_entity;
  if (!entId) return;
  await espAction(entId, "install");
}

async function checkSystemUpdates() {
  showToast("Checking every Device for firmware updates…");
  const data = await callStudioCommand({command: "check_system_updates"});
  if (data) {
    applyStateToDom(data, false);
    const chk = data.update_check || {};
    if (!chk.checked) {
      showToast("No Device reports a firmware update entity");
    } else if (chk.available) {
      showToast(`Firmware updates available for ${fmtNumber(chk.available)} of ${fmtNumber(chk.checked)} Devices`);
    } else {
      showToast(`All ${fmtNumber(chk.checked)} Devices are up to date`);
    }
  }
}

function openDevicesLanding() {
  DEVICE_SELECTED = false;
  setScope("device", "select_device_prompt");
}

function openDevicesWithCategory(categoryKey) {
  DEVICE_CATEGORY_FILTER = categoryKey || "all";
  const sel = doc.getElementById("device-category-filter");
  if (sel) sel.value = DEVICE_CATEGORY_FILTER;
  DEVICE_SELECTED = false;
  setScope("device", "select_device_prompt");
  window.scrollTo({top: 0, behavior: "smooth"});
}

function openSystemSection(viewId, cardId) {
  setScope("system", viewId);
  if (cardId) {
    setTimeout(() => {
      const el = doc.getElementById(cardId);
      if (el) el.scrollIntoView({behavior: "smooth", block: "start"});
    }, 60);
  } else {
    window.scrollTo({top: 0, behavior: "smooth"});
  }
}

function setScope(scope, targetView=null) {
  CURRENT_SCOPE = scope === "system" ? "system" : "device";
  doc.getElementById("tab-scope-system").classList.toggle("active", CURRENT_SCOPE === "system");
  doc.getElementById("tab-scope-device").classList.toggle("active", CURRENT_SCOPE === "device");
  updateTopHeaderForScope();

  if (CURRENT_SCOPE === "system") {
    switchView(targetView || "system_overview", null);
  } else if (!DEVICE_SELECTED) {
    switchView("select_device_prompt", null);
  } else {
    switchView(targetView || "dashboard", null);
  }
  if (STATE) {
    renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config);
  }
}

function switchView(viewId, btnEl) {
  const neededScope = SYSTEM_VIEWS.includes(viewId) ? "system" : "device";
  if (CURRENT_SCOPE !== neededScope) {
    setScope(neededScope, viewId);
    return;
  }
  if (CURRENT_SCOPE === "device" && !DEVICE_SELECTED && viewId !== "select_device_prompt") {
    viewId = "select_device_prompt";
  }
  doc.querySelectorAll("aside .nav-btn").forEach(b => b.classList.remove("active"));
  if (btnEl) {
    btnEl.classList.add("active");
  } else {
    const matchBtn = doc.querySelector(`aside .nav-btn[data-view="${viewId}"]`);
    if (matchBtn) matchBtn.classList.add("active");
  }
  ALL_VIEWS.forEach(id => {
    const el = doc.getElementById("view-" + id);
    if (el) el.classList.toggle("hidden", id !== viewId);
  });
  if (viewId !== "area_tracking" && POLL_TIMER) stopSurveyFastMode();
  updateUnifiedPageTitle(viewId);
  syncUrlToView(viewId);
}

// The URL follows the page (/latter, /latter/devices/<id>[/<page>], /latter/system/<page>), so a reload or
// Back keeps the user's place. Navigation uses the history API plus Home Assistant's location-changed event.
const DEVICE_VIEW_SLUGS = {dashboard: "overview", home_display: "display", audio_voice: "audio", power: "power", system: "settings"};
const SYSTEM_VIEW_SLUGS = {system_overview: "overview", shared_entities: "shared", remotes: "remotes", system_sync: "groups", area_tracking: "presence", system_admin: "settings"};
const slugToView = (map, slug) => Object.keys(map).find(k => map[k] === slug);
let ROUTE_APPLYING = false;

function studioPathFor(viewId) {
  const prefix = HOST_ELEMENT?.route?.prefix || "/latter";
  if (SYSTEM_VIEW_SLUGS[viewId]) return `${prefix}/system/${SYSTEM_VIEW_SLUGS[viewId]}`;
  if (viewId === "select_device_prompt" || !DEVICE_SELECTED || !ACTIVE_SUBENTRY_ID) return prefix;
  const slug = DEVICE_VIEW_SLUGS[viewId] || "overview";
  return `${prefix}/devices/${encodeURIComponent(ACTIVE_SUBENTRY_ID)}${slug === "overview" ? "" : `/${slug}`}`;
}

function syncUrlToView(viewId) {
  if (ROUTE_APPLYING || !HOST_ELEMENT?.isConnected) return;
  const path = studioPathFor(viewId);
  if (window.location.pathname === path) return;
  try {
    window.history.pushState(null, "", path);
  } catch (_e) {
    return;
  }
  window.dispatchEvent(new CustomEvent("location-changed", {detail: {replace: false}}));
}

function navigateToView(viewId) {
  switchView(viewId, null);
  window.scrollTo({top: 0, behavior: "smooth"});
}

function selectCurrentDevice() {
  if (ACTIVE_SUBENTRY_ID) {
    switchSystemDevice(ACTIVE_SUBENTRY_ID);
    return;
  }
  DEVICE_SELECTED = true;
  if (STATE) {
    applyStateToDom(STATE, {system: false, device: true});
  }
  setScope("device", "dashboard");
}

async function switchSystemDevice(targetRef) {
  if (!targetRef) {
    DEVICE_SELECTED = false;
    setScope("device", "select_device_prompt");
    return;
  }
  const subId = String(targetRef).includes("/devices/")
    ? String(targetRef).split("/devices/").pop().split("?")[0]
    : String(targetRef);
  const changed = ACTIVE_SUBENTRY_ID !== subId;
  ACTIVE_SUBENTRY_ID = subId;
  DEVICE_SELECTED = true;
  if (changed || !STATE) {
    await flushSettings("device");
    await refreshState({system: canReloadForm("system"), device: true});
    if (HOST_ELEMENT && typeof HOST_ELEMENT._resubscribe === "function") {
      await HOST_ELEMENT._resubscribe(false);
    }
  } else {
    applyStateToDom(STATE, {system: false, device: true});
  }
  setScope("device", "dashboard");
}

function populateSelect(selId, items, selectedVal, allowEmpty=true) {
  const sel = doc.getElementById(selId);
  if (!sel) return;
  sel.innerHTML = "";
  if (allowEmpty) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— None / Auto —";
    sel.appendChild(opt);
  }
  (items || []).forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.name;
    if (item.id === selectedVal) opt.selected = true;
    sel.appendChild(opt);
  });
}

function renderDockPillsFromInput() {
  const box = doc.getElementById("dock-pills-container");
  const inp = doc.getElementById("cfg-dock_apps");
  if (!box || !inp) return;
  const rawTokens = inp.value.split(/[,;| ]+/).map(t => t.trim().toLowerCase()).filter(Boolean);
  const activeTokens = [];
  rawTokens.forEach(t => {
    if (DOCK_APP_META.some(m => m.token === t) && !activeTokens.includes(t)) activeTokens.push(t);
  });
  const disabledTokens = DOCK_APP_META.map(m => m.token).filter(t => !activeTokens.includes(t));
  box.innerHTML = activeTokens.concat(disabledTokens).map((tok) => {
    const meta = DOCK_APP_META.find(m => m.token === tok);
    const label = meta ? meta.label : tok;
    const isEn = activeTokens.includes(tok);
    const actIdx = activeTokens.indexOf(tok);
    const canLeft = isEn && actIdx > 0;
    const canRight = isEn && actIdx < activeTokens.length - 1;
    return `<span class="pill ${isEn ? 'enabled' : ''}">
      ${canLeft ? `<button type="button" class="pill-move" aria-label="Move ${esc(label)} left" onclick="moveDockAppToken(${jsArg(tok)}, -1)">◀</button>` : ''}
      <button type="button" class="pill-toggle" aria-pressed="${isEn}" onclick="toggleDockAppToken(${jsArg(tok)})">${isEn ? '✓ ' : '+ '}${esc(label)}</button>
      ${canRight ? `<button type="button" class="pill-move" aria-label="Move ${esc(label)} right" onclick="moveDockAppToken(${jsArg(tok)}, 1)">▶</button>` : ''}
    </span>`;
  }).join("");
}

function toggleDockAppToken(tok) {
  const inp = doc.getElementById("cfg-dock_apps");
  if (!inp) return;
  let active = inp.value
    .split(/[,;| ]+/)
    .map(t => t.trim().toLowerCase())
    .filter(t => DOCK_APP_META.some(m => m.token === t));
  if (active.includes(tok)) {
    if (active.length <= 1) return;
    active = active.filter(t => t !== tok);
  } else {
    active.push(tok);
  }
  inp.value = active.join(",");
  saveSetting("device", "dock_apps", 600);
  renderDockPillsFromInput();
}

function moveDockAppToken(tok, dir) {
  const inp = doc.getElementById("cfg-dock_apps");
  if (!inp) return;
  const active = inp.value
    .split(/[,;| ]+/)
    .map(t => {
      const v = t.trim().toLowerCase();
      return v;
    })
    .filter(t => DOCK_APP_META.some(m => m.token === t));
  const idx = active.indexOf(tok);
  const swapIdx = idx + dir;
  if (idx < 0 || swapIdx < 0 || swapIdx >= active.length) return;
  const tmp = active[idx];
  active[idx] = active[swapIdx];
  active[swapIdx] = tmp;
  inp.value = active.join(",");
  saveSetting("device", "dock_apps", 600);
  renderDockPillsFromInput();
}

function toggleSurveyFastMode(enabled) {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  POLL_TIMER = null;
  if (!enabled) return;
  POLL_TIMER = setInterval(() => refreshState(false), 1500);
  refreshState(false);
}

// Fast refresh only polls while the BLE & Area Presence page is open.
function stopSurveyFastMode() {
  const sw = doc.getElementById("survey-fast-mode");
  if (sw) sw.checked = false;
  toggleSurveyFastMode(false);
}

function renderRssiBars(surveyRows, packetsSeen) {
  const box = doc.getElementById("rssi-container");
  if (!box) return;
  const rows = surveyRows || [];
  if (!rows.length) {
    box.innerHTML = emptyStateHtml(`No Bluetooth proxy has heard this Device yet (packets seen: ${packetsSeen || 0}).`);
    return;
  }
  box.innerHTML = rows.map(r => {
    const hasSignal = r.raw_rssi !== null && r.raw_rssi !== undefined;
    const eff = hasSignal ? r.effective_rssi : -100;
    const pct = hasSignal ? Math.max(6, Math.min(100, Math.round(((eff + 100) / 55) * 100))) : 0;
    const offSign = r.offset_db > 0 ? `+${r.offset_db}` : `${r.offset_db}`;
    const ageText = hasSignal ? fmtAgo(r.age_seconds) : "No signal yet";
    const dist = (hasSignal && r.distance_m != null) ? ` • ~${fmtDistance(r.distance_m)}` : "";
    const sig = hasSignal
      ? `Raw ${fmtNumber(r.raw_rssi)} dBm • Offset ${offSign} dB → Effective ${fmtNumber(r.effective_rssi)} dBm${dist}`
      : `Offset ${offSign} dB • Waiting for a beacon packet`;
    const areaArg = jsArg(r.area_id);
    return `<div class="signal-row ${r.is_winner ? 'winner' : ''}">
      <div class="signal-row-head">
        <div class="signal-row-title">
          <strong>${esc(r.area_name)}</strong>
          <span class="signal-meta">${esc(r.scanner)} • ${esc(ageText)}</span>
          ${r.is_winner ? '<span class="chip chip-success">Active</span>' : ''}
        </div>
        <div class="input-action-row">
          <button type="button" class="btn btn-secondary btn-compact" aria-label="Lower the offset by 1 dB" onclick="setBleOffset(${areaArg}, ${Number(r.offset_db) - 1})">−1 dB</button>
          <span class="chip">${esc(offSign)} dB</span>
          <button type="button" class="btn btn-secondary btn-compact" aria-label="Raise the offset by 1 dB" onclick="setBleOffset(${areaArg}, ${Number(r.offset_db) + 1})">+1 dB</button>
          ${r.offset_db !== 0 ? `<button type="button" class="btn btn-text btn-compact" onclick="setBleOffset(${areaArg}, 0)">Reset</button>` : ''}
          <button type="button" class="btn btn-secondary btn-compact" onclick="autoCalibrateHere(${areaArg})">Calibrate current Area</button>
        </div>
      </div>
      <div class="signal-meta">${esc(sig)}</div>
      <div class="signal-track"><div class="signal-fill ${hasSignal ? '' : 'no-signal'}" style="--signal-pct:${pct}%"></div></div>
    </div>`;
  }).join("");
}

function renderSystemOverview(systemDevices, systemControls, cfg) {
  const countBadge = doc.getElementById("nav-system-count");
  if (countBadge) countBadge.textContent = String((systemDevices || []).length);

  const groups = STATE?.device_groups || [];
  const profiles = STATE?.saved_profiles || [];

  // Pickers for System actions that act on one Device: the action names its Device (studio-design.md section 5).
  const allDevices = systemDevices || [];
  const latterDevices = allDevices.filter(d => d.kind !== "ble_tag");
  fillDevicePicker("profile-source-device", latterDevices, "— Choose a Device —");
  fillDevicePicker("doorbell-test-device", latterDevices, "— Choose a Device —");
  fillDevicePicker("bkp-restore-device", allDevices, "— Choose a Device —");
  fillDevicePicker("bkp-scope-select", allDevices, null, [{value: "system", label: "Full System & all Devices"}], "device:");

  const quickProfSel = doc.getElementById("quick-profile-select");
  if (quickProfSel && profiles.length) {
    const prevP = quickProfSel.value;
    quickProfSel.innerHTML = profiles.map(p =>
      `<option value="${esc(p.id)}" ${p.id === prevP ? 'selected' : ''}>${esc(p.name)}</option>`
    ).join("");
  }

  const devGrpSel = doc.getElementById("cfg-device_group");
  if (devGrpSel && groups.length) {
    const curGrp = canReloadForm("device") ? (cfg?.device_group || "unassigned") : devGrpSel.value;
    devGrpSel.innerHTML = groups.map(g =>
      `<option value="${esc(g.id)}" ${g.id === curGrp ? 'selected' : ''}>${esc(g.name)}</option>`
    ).join("");
  }

  const targetScopes = [
    {id: "", name: "— Choose where to apply —"},
    {id: "all", name: `All Devices (${allDevices.length})`}
  ];
  groups.forEach(g => {
    const cnt = allDevices.filter(d => d.device_group === g.id).length;
    targetScopes.push({id: `group:${g.id}`, name: `Group: ${g.name} (${cnt})`});
  });
  allDevices.forEach(d => targetScopes.push({id: `device:${d.subentry_id}`, name: `Device: ${d.title}`}));
  const profScopeSel = doc.getElementById("profile-target-scope");
  if (profScopeSel) {
    const prevVal = profScopeSel.value || "";
    profScopeSel.innerHTML = targetScopes.map(o =>
      `<option value="${esc(o.id)}" ${o.id === prevVal ? 'selected' : ''}>${esc(o.name)}</option>`
    ).join("");
  }

  const grpFilterSel = doc.getElementById("group-ctrl-filter");
  let activeFilter = "all";
  if (grpFilterSel) {
    activeFilter = grpFilterSel.value || "all";
    const filterOpts = [{id: "all", name: `All Devices (${allDevices.length})`}];
    groups.forEach(g => {
      const cnt = allDevices.filter(d => d.device_group === g.id).length;
      filterOpts.push({id: `group:${g.id}`, name: `Group: ${g.name} (${cnt})`});
    });
    filterOpts.push({id: "trait:roaming", name: "Roaming Devices"});
    filterOpts.push({id: "trait:stationary", name: "Stationary Devices"});
    grpFilterSel.innerHTML = filterOpts.map(o =>
      `<option value="${esc(o.id)}" ${o.id === activeFilter ? 'selected' : ''}>${esc(o.name)}</option>`
    ).join("");
  }

  const catSel = doc.getElementById("device-category-filter");
  if (catSel) {
    const baseOpts = [
      {id: "all", label: "All Devices"},
      {id: "online", label: "Online Devices"},
      {id: "native", label: "Latter-native Devices"},
      {id: "ble_tracked", label: "BLE-tracked Devices"},
      {id: "assigned_person", label: "Devices with an assigned person"},
      {id: "roaming", label: "Roaming Devices"},
      {id: "stationary", label: "Stationary Devices"},
      {id: "headless", label: "Screenless Devices"},
      {id: "ble_tag", label: "BLE phones, watches & tags"},
      {id: "updates", label: "Firmware update available"}
    ];
    groups.forEach(g => {
      if (g && g.id && g.id !== "unassigned") baseOpts.push({id: `group:${g.id}`, label: `Group: ${g.name}`});
    });
    catSel.innerHTML = baseOpts.map(o =>
      `<option value="${esc(o.id)}" ${o.id === DEVICE_CATEGORY_FILTER ? 'selected' : ''}>${esc(o.label)}</option>`
    ).join("");
  }

  const statusRank = (st) => (st === "Update available" ? 1 : (st === "Offline" ? 2 : 3));
  const cat = DEVICE_CATEGORY_FILTER || "all";
  const filteredDevices = allDevices.filter(d => {
    const isBleTag = d.kind === "ble_tag";
    const isRoaming = isBleTag || !!d.is_roaming;
    if (cat === "online") return !!d.is_online;
    if (cat === "native") return !!d.is_latter_native;
    if (cat === "ble_tracked") return !!d.ble_tracked;
    if (cat === "assigned_person") return !!d.assigned_person;
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "headless") return isBleTag || !d.has_display;
    if (cat === "ble_tag") return isBleTag;
    if (cat === "updates") return d.status_label === "Update available";
    if (cat.startsWith("group:")) return d.device_group === cat.split(":", 2)[1];
    return true;
  });
  filteredDevices.sort((a, b) => {
    let cmp = 0;
    if (DEVICE_SORT_COL === "status") {
      cmp = statusRank(a.status_label) - statusRank(b.status_label);
      if (cmp === 0) cmp = (a.title || "").localeCompare(b.title || "");
    } else if (DEVICE_SORT_COL === "model") {
      cmp = (a.model_label || "").localeCompare(b.model_label || "");
    } else if (DEVICE_SORT_COL === "area") {
      cmp = (a.area_label || "").localeCompare(b.area_label || "");
    } else if (DEVICE_SORT_COL === "group") {
      cmp = (a.device_group_name || "").localeCompare(b.device_group_name || "");
    } else {
      cmp = (a.title || "").localeCompare(b.title || "");
    }
    return DEVICE_SORT_ASC ? cmp : -cmp;
  });

  // Sortable, keyboard-accessible table: header buttons sort, rows open with Enter or Space.
  const sortTh = (col, label) => {
    const sorted = DEVICE_SORT_COL === col;
    const aria = sorted ? (DEVICE_SORT_ASC ? "ascending" : "descending") : "none";
    return `<th aria-sort="${aria}"><button type="button" class="sort-btn" onclick="toggleDeviceTableSort('${col}')">${label}${sorted ? (DEVICE_SORT_ASC ? " ▲" : " ▼") : ""}</button></th>`;
  };
  const tableRowsHtml = filteredDevices.map(d => {
    const act = d.is_current ? "selectCurrentDevice()" : `switchSystemDevice(${jsArg(d.subentry_id)})`;
    const st = d.status_label || "—";
    const dotCls = st === "Update available" ? "update" : (st === "Offline" ? "" : "online");
    return `<tr tabindex="0" aria-label="Open ${esc(d.title)}" onclick="${act}" onkeydown="if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); ${act}; }">
      <td class="col-name">${esc(d.title)}</td>
      <td>${esc(d.model_label || "—")}</td>
      <td>${esc(d.area_label || "—")}</td>
      <td>${esc(d.device_group_name || "—")}</td>
      <td><span class="status-dot ${dotCls}"></span>${esc(st)}</td>
      <td class="col-open" aria-hidden="true">›</td>
    </tr>`;
  }).join("");
  const promptBox = doc.getElementById("prompt-devices-list");
  if (promptBox) {
    promptBox.innerHTML = filteredDevices.length
      ? `<div class="table-wrap"><table class="data-table">
          <thead><tr>${sortTh("title", "Device")}${sortTh("model", "Model")}${sortTh("area", "Area")}${sortTh("group", "Group")}${sortTh("status", "Status")}<th><span class="sort-btn" aria-hidden="true"></span></th></tr></thead>
          <tbody>${tableRowsHtml}</tbody>
        </table></div>`
      : emptyStateHtml(allDevices.length ? "No Devices match this category." : "No Devices yet. Latter displays appear here after you add them in Home Assistant.");
  }

  // System overview counts
  const onlineDevs = allDevices.filter(d => d.is_online).length;
  const setSysTxt = (id, val) => {
    const el = doc.getElementById(id);
    if (el) el.textContent = String(val);
  };
  setSysTxt("sys-sum-version", STATE?.version ? `v${String(STATE.version).replace(/^v/i, "")}` : "—");
  setSysTxt("sys-sum-online", `${onlineDevs} / ${allDevices.length}`);
  setSysTxt("sys-sum-native", allDevices.filter(d => d.is_latter_native).length);
  setSysTxt("sys-sum-ble-tracked", allDevices.filter(d => d.ble_tracked).length);
  setSysTxt("sys-sum-people", allDevices.filter(d => d.assigned_person).length);
  setSysTxt("sys-sum-proxies", STATE?.ble_proxy_count ?? "—");
  const sysCfg = STATE?.system_config || {};
  setSysTxt("sys-sum-remotes", (sysCfg.remotes_list || []).length);
  setSysTxt("sys-sum-vol", (sysCfg.volume_overrides || []).length);
  setSysTxt("sys-sum-cameras", (sysCfg.camera_entities || []).length);
  setSysTxt("sys-sum-calendars", (sysCfg.calendar_entities || []).length);
  setSysTxt("sys-sum-groups-profiles", `${groups.length} group${groups.length === 1 ? "" : "s"} / ${profiles.length} profile${profiles.length === 1 ? "" : "s"}`);

  renderAnnounceTargets();

  const profBox = doc.getElementById("saved-profiles-list");
  if (profBox) {
    profBox.innerHTML = profiles.length
      ? profiles.map(p => {
          const ctrlCnt = Object.keys(p.esphome_controls || {}).length;
          const isBuiltin = String(p.id || "").startsWith("preset_");
          return settingsRowHtml(
            `${esc(p.name)} <span class="chip">${ctrlCnt} controls</span>`,
            esc(p.description || ""),
            `<button type="button" class="btn btn-secondary btn-compact" onclick="applySavedProfile(${jsArg(p.id)})">Apply</button>
             ${isBuiltin ? "" : iconButtonHtml(ICON_DELETE, `Delete profile ${p.name}`, `deleteSavedProfile(${jsArg(p.id)})`, "danger")}`
          );
        }).join("")
      : emptyStateHtml("No profiles saved yet.");
  }

  const grpBox = doc.getElementById("device-groups-list");
  if (grpBox) {
    grpBox.innerHTML = groups.map(g => {
      const members = allDevices.filter(d => d.device_group === g.id);
      const isDefault = ["unassigned", "handhelds", "bedrooms", "common_areas", "wall_panels", "sensors"].includes(g.id);
      const desc = [g.description || "", members.length ? `Devices: ${members.map(m => m.title).join(", ")}` : "No Devices"].filter(Boolean).join(" • ");
      return settingsRowHtml(
        `${esc(g.name)} <span class="chip">${members.length}</span>`,
        esc(desc),
        isDefault ? "" : iconButtonHtml(ICON_DELETE, `Delete group ${g.name}`, `deleteDeviceGroup(${jsArg(g.id)})`, "danger")
      );
    }).join("");
  }

  const fBox = doc.getElementById("system-controls-list");
  if (fBox) {
    if (!systemControls || !systemControls.length) {
      fBox.innerHTML = emptyStateHtml("No shared Device controls found.");
    } else {
      const activeCat = doc.getElementById("group-ctrl-cat-filter")?.value || "display";
      const rows = systemControls.map(fc => {
        if (activeCat !== "all" && fc.section !== activeCat) return "";
        const targets = (fc.targets || []).filter(t => {
          if (activeFilter === "all") return true;
          if (activeFilter.startsWith("group:")) return t.device_group === activeFilter.split(":")[1];
          if (activeFilter === "trait:roaming") return !!t.is_roaming;
          if (activeFilter === "trait:stationary") return !t.is_roaming;
          return true;
        });
        if (!targets.length) return "";
        const idsArg = jsArg(targets.map(t => t.entity_id));
        const states = [...new Set(targets.map(t => String(t.state ?? "")))];
        const mixed = states.length > 1;
        const curState = mixed ? "" : states[0];
        let widget = `<span class="chip">${esc(mixed ? "Mixed" : curState)}</span>`;
        if (fc.domain === "select" && fc.options && fc.options.length) {
          const opts = (mixed ? [`<option value="" selected disabled>Mixed</option>`] : []).concat(
            fc.options.map(o => `<option value="${esc(o)}" ${o === curState ? 'selected' : ''}>${esc(o)}</option>`)
          ).join("");
          widget = `<select aria-label="${esc(fc.name)}" onchange="bulkSelect(${idsArg}, this.value)">${opts}</select>`;
        } else if (fc.domain === "switch") {
          widget = `${mixed ? `<span class="chip">Mixed</span>` : ""}<input type="checkbox" class="switch" role="switch" aria-label="${esc(fc.name)}" ${curState === "on" ? "checked" : ""} onchange="bulkToggle(${idsArg}, this.checked ? 'turn_on' : 'turn_off')">`;
        } else if (fc.domain === "number") {
          const numVal = mixed ? (fc.min ?? 0) : (parseFloat(curState) || 0);
          widget = `<input type="range" aria-label="${esc(fc.name)}" min="${esc(fc.min ?? 0)}" max="${esc(fc.max ?? 100)}" step="${esc(fc.step ?? 1)}" value="${esc(numVal)}" onchange="bulkNumber(${idsArg}, this.value)"><span class="chip">${esc(mixed ? "Mixed" : `${curState} ${fc.unit || ""}`.trim())}</span>`;
        }
        const desc = `${fc.section_title} • ${targets.length} Device${targets.length > 1 ? "s" : ""}${mixed ? " • Mixed values" : ""}`;
        return settingsRowHtml(esc(fc.name), esc(desc), widget);
      }).filter(Boolean).join("");
      fBox.innerHTML = rows || emptyStateHtml("No Devices match this filter.");
    }
  }
}

function fillDevicePicker(selId, devices, placeholder, leadOptions = [], valuePrefix = "") {
  const sel = doc.getElementById(selId);
  if (!sel) return;
  const prev = sel.value;
  const opts = (leadOptions || []).map(o => ({value: o.value, label: o.label}));
  (devices || []).forEach(d => opts.push({value: `${valuePrefix}${d.subentry_id}`, label: `Device: ${d.title}`}));
  const head = placeholder ? `<option value="">${esc(placeholder)}</option>` : "";
  sel.innerHTML = head + opts.map(o =>
    `<option value="${esc(o.value)}" ${o.value === prev ? 'selected' : ''}>${esc(o.label)}</option>`
  ).join("");
}

async function applyQuickProfileFromOverview() {
  const sel = doc.getElementById("quick-profile-select");
  if (!sel || !sel.value || !ACTIVE_SUBENTRY_ID) return;
  const data = await callStudioCommand({command: "apply_profile", profile_id: sel.value, target_scope: `device:${ACTIVE_SUBENTRY_ID}`});
  if (data) {
    applyStateToDom(data, true);
    showToast("Applied configuration profile to device");
  }
}

async function bulkSelect(entityIds, option) {
  const data = await callStudioCommand({command: "system_entity_action", entity_ids: entityIds, option});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Applied '${option}' across ${entityIds.length} device(s)`);
  }
}

async function bulkToggle(entityIds, action) {
  const data = await callStudioCommand({command: "system_entity_action", entity_ids: entityIds, action});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Applied ${action} across ${entityIds.length} device(s)`);
  }
}

async function bulkNumber(entityIds, level) {
  const data = await callStudioCommand({command: "system_entity_action", entity_ids: entityIds, level});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Applied ${level} across ${entityIds.length} device(s)`);
  }
}

async function setBleOffset(areaId, offsetDb) {
  const data = await callStudioCommand({command: "set_ble_area_offset", area_id: areaId, offset_db: offsetDb});
  if (data) {
    applyStateToDom(data, false);
    showToast("Saved BLE area offset");
  }
}

function onSelectBleSurveyDevice(subentryId) {
  SELECTED_SURVEY_ID = subentryId || "";
  if (SELECTED_SURVEY_ID) {
    localStorage.setItem("latter_ble_survey_subentry", SELECTED_SURVEY_ID);
  }
  renderActiveSurveyDeviceBars();
}

function renderActiveSurveyDeviceBars() {
  if (!STATE) return;
  renderAreaPresenceGrid();
  renderDiscoveredBleTable();
  const allDevs = STATE.system_devices || [];
  const bleDevs = allDevs.filter(d => d.has_ble);
  const picker = doc.getElementById("ble-survey-device-picker");

  if (!bleDevs.length) {
    if (picker) picker.innerHTML = `<option value="">No BLE devices found</option>`;
    renderRssiBars([], 0);
    return;
  }

  let activeDev = bleDevs.find(d => d.subentry_id === SELECTED_SURVEY_ID);
  if (!activeDev) {
    activeDev = bleDevs.find(d => d.is_current) || bleDevs[0];
    SELECTED_SURVEY_ID = activeDev.subentry_id;
    localStorage.setItem("latter_ble_survey_subentry", SELECTED_SURVEY_ID);
  }

  if (picker) {
    picker.innerHTML = bleDevs.map(d =>
      `<option value="${esc(d.subentry_id)}" ${d.subentry_id === SELECTED_SURVEY_ID ? 'selected' : ''}>${esc(d.title)} (${esc(d.active_area_name)})</option>`
    ).join("");
  }

  const rows = Array.isArray(activeDev.ble_survey_rows)
    ? activeDev.ble_survey_rows
    : (activeDev.is_current ? (STATE.live?.ble_survey_rows || []) : []);
  const pkts = (activeDev.ble_packets_seen !== undefined)
    ? activeDev.ble_packets_seen
    : (activeDev.is_current ? (STATE.live?.ble_packets_seen || 0) : 0);

  renderRssiBars(rows, pkts);
}

function renderAreaPresenceGrid() {
  const box = doc.getElementById("area-presence-grid-box");
  if (!box) return;
  // Don't rebuild the list under a control the user is using (a slider drag or an open select).
  const activeEl = getStudioActiveElement();
  if (activeEl && box.contains(activeEl) && ["INPUT", "SELECT"].includes(activeEl.tagName)) return;
  const rows = STATE?.live?.area_presence_grid || [];
  if (!rows.length) {
    box.innerHTML = emptyStateHtml("No Bluetooth proxies or Area occupancy sensors found yet.");
    return;
  }
  const modeOptions = [
    {val: "weighted", label: "Weighted (BLE and sensors)"},
    {val: "any_or", label: "Either (BLE or a sensor)"},
    {val: "ble_only", label: "BLE only"},
    {val: "ble_and_sensor", label: "Both (BLE and a sensor)"}
  ];
  box.innerHTML = rows.map(r => {
    const isOcc = !!r.is_occupied;
    const occNames = (r.occupant_names && r.occupant_names.length)
      ? r.occupant_names.join(", ")
      : (isOcc ? "Occupied (sensor)" : "Empty");
    const parts = [occNames];
    if (r.winning_rssi !== null && r.winning_rssi !== undefined) {
      parts.push(`BLE ${fmtNumber(r.winning_rssi)} dBm${r.closest_distance_m != null ? ` (~${fmtDistance(r.closest_distance_m)})` : ""}`);
    }
    if (r.active_sensors && r.active_sensors.length) {
      parts.push(`${r.active_sensors.length} active sensor${r.active_sensors.length > 1 ? "s" : ""}`);
    } else if (r.available_sensors && r.available_sensors.length) {
      parts.push(`${r.available_sensors.length} sensor${r.available_sensors.length > 1 ? "s" : ""} clear`);
    }
    if (r.floor_id) parts.push(`Floor: ${r.floor_id}`);
    const curMode = r.fusion_mode || "weighted";
    const areaArg = jsArg(r.area_id);
    const opts = modeOptions.map(m => `<option value="${esc(m.val)}" ${m.val === curMode ? 'selected' : ''}>${esc(m.label)}</option>`).join("");
    const chip = isOcc
      ? `<span class="chip chip-success">Occupied • ${esc(fmtPercent(r.confidence_pct))}</span>`
      : `<span class="chip">Clear</span>`;
    const threshold = Number(r.fusion_threshold_pct || 50);
    const chosen = r.fusion_sensors || [];
    const choices = r.fusion_sensor_choices || [];
    const sensorPills = choices.length
      ? `<div class="pill-list">${choices.map(s => {
          const on = chosen.includes(s.entity_id);
          return `<span class="pill ${on ? "enabled" : ""}"><button type="button" class="pill-toggle" aria-pressed="${on}" title="${esc(s.entity_id)}" onclick="toggleFusionSensor(${areaArg}, ${jsArg(s.entity_id)})">${on ? "✓ " : ""}${esc(s.name)}</button></span>`;
        }).join("")}</div>`
      : emptyStateHtml("This Area has no occupancy, motion or door sensors.");
    const thresholdId = `fusion-threshold-${esc(r.area_id)}`;
    return `<div class="fusion-area">
      ${settingsRowHtml(
        `${esc(r.area_name)} ${chip}`,
        esc(parts.join(" • ")),
        `<select aria-label="Fusion mode for ${esc(r.area_name)}" onchange="setAreaFusion(${areaArg}, {mode: this.value})">${opts}</select>`
      )}
      <details class="sub-collapsible" ${FUSION_OPEN_AREAS.has(r.area_id) ? "open" : ""} ontoggle="onFusionDetailsToggle(${areaArg}, this.open)">
        <summary>Fusion settings</summary>
        <div class="card-content settings-list">
          ${settingsRowHtml(
            `<label for="${thresholdId}">Occupied at</label>`,
            curMode === "weighted"
              ? "The Area counts as occupied when the combined BLE and sensor score reaches this."
              : "Used by the Weighted mode only.",
            `<input type="range" id="${thresholdId}" min="20" max="95" step="5" value="${esc(threshold)}" ${curMode === "weighted" ? "" : "disabled"}
               oninput="this.nextElementSibling.textContent = fmtPercent(Number(this.value))"
               onchange="setAreaFusion(${areaArg}, {threshold_pct: Number(this.value)})"><span class="chip">${esc(fmtPercent(threshold))}</span>`
          )}
          <div class="settings-row stacked">
            <div class="settings-row-text"><span class="row-label">Sensors that count</span><p class="row-description">${chosen.length ? `${chosen.length} of ${choices.length} selected.` : "None selected: every sensor in this Area counts."}</p></div>
            <div class="settings-row-control">${sensorPills}</div>
          </div>
        </div>
      </details>
    </div>`;
  }).join("");
}

const FUSION_OPEN_AREAS = new Set();

function onFusionDetailsToggle(areaId, isOpen) {
  if (isOpen) FUSION_OPEN_AREAS.add(areaId);
  else FUSION_OPEN_AREAS.delete(areaId);
}

function toggleFusionSensor(areaId, entityId) {
  const row = (STATE?.live?.area_presence_grid || []).find(r => r.area_id === areaId);
  const current = row?.fusion_sensors || [];
  const next = current.includes(entityId) ? current.filter(s => s !== entityId) : current.concat([entityId]);
  setAreaFusion(areaId, {sensors: next});
}

async function setAreaFusion(areaId, changes) {
  const data = await callStudioCommand({command: "set_area_fusion", area_id: areaId, ...changes});
  if (data) {
    applyStateToDom(data, false);
    showToast("Saved Area sensor fusion");
  }
}

function renderDiscoveredBleTable() {
  const box = doc.getElementById("ble-adopt-table-box");
  if (!box) return;
  const cands = STATE?.discovered_ble_devices || [];
  if (!cands.length) {
    box.innerHTML = emptyStateHtml("No unadopted Bluetooth devices nearby.");
    return;
  }
  const persons = STATE?.catalog?.persons || [];
  box.innerHTML = cands.map((c, idx) => {
    const pOpts = [`<option value="">No person</option>`].concat(
      persons.map(p => `<option value="${esc(p.id)}">${esc(p.friendly || p.name)}</option>`)
    ).join("");
    const meta = [c.kind || "BLE device", c.target_address];
    if (c.rssi !== null && c.rssi !== undefined) meta.push(`${fmtNumber(c.rssi)} dBm`);
    if (c.area_name) meta.push(`Nearest Area: ${c.area_name}`);
    return settingsRowHtml(
      esc(c.title),
      esc(meta.join(" • ")),
      `<select id="ble-adopt-person-${idx}" aria-label="Assigned person for ${esc(c.title)}">${pOpts}</select>
       <button type="button" class="btn btn-secondary btn-compact" onclick="quickAdoptBleCandidate(${idx})">Adopt</button>`
    );
  }).join("");
}

async function quickAdoptBleCandidate(idx) {
  const cands = STATE?.discovered_ble_devices || [];
  const cand = cands[idx];
  if (!cand) return;
  const assigned_person = doc.getElementById(`ble-adopt-person-${idx}`)?.value || "";
  const data = await callStudioCommand({
      command: "add_ble_device",
      name: cand.title,
      target_address: cand.target_address,
      assigned_person
    });
  if (data) {
    applyStateToDom(data, false);
    showToast(`Adopted BLE device '${cand.title}'`);
  }
}

async function autoCalibrateHere(areaId) {
  if (!SELECTED_SURVEY_ID) {
    showToast("Failed: select the BLE survey device first", "error");
    return;
  }
  const data = await callStudioCommand({
    command: "auto_calibrate_here",
    area_id: areaId,
    survey_subentry_id: SELECTED_SURVEY_ID
  });
  if (data) {
    applyStateToDom(data, false);
    showToast("Calibrated current area offset");
  }
}

function renderCameraPreview(camEntityId) {
  const box = doc.getElementById("cam-preview-box");
  const img = doc.getElementById("cam-preview-img");
  const lbl = doc.getElementById("cam-preview-label");
  if (!box || !img) return;
  if (!camEntityId) {
    box.classList.add("hidden");
    return;
  }
  const camObj = (STATE?.catalog?.cameras || []).find(c => c.id === camEntityId);
  if (!camObj || !camObj.preview_url) {
    box.classList.add("hidden");
    showToast("Save the cameras and open a Device to preview this camera", "error");
    return;
  }
  PREVIEW_CAMERA_ENTITY = camEntityId;
  if (lbl) lbl.textContent = `Preview: ${camEntityId}`;
  img.src = camObj.preview_url;
  box.classList.remove("hidden");
}

function refreshActiveCameraPreview() {
  if (PREVIEW_CAMERA_ENTITY) {
    renderCameraPreview(PREVIEW_CAMERA_ENTITY);
  }
}

async function testDoorbellSpeaker() {
  const subentryId = doc.getElementById("doorbell-test-device")?.value || "";
  const camera = (STATE?.system_config?.camera_entities || [])[0] || "";
  if (!subentryId) {
    showToast("Failed: choose the Device to test from", "error");
    return;
  }
  if (!camera) {
    showToast("Failed: add a camera and save first", "error");
    return;
  }
  const data = await callStudioCommand({
    command: "test_doorbell_speaker",
    subentry_id: subentryId,
    camera_entity: camera,
    message: "This is a test of the Latter door speaker."
  });
  if (data) {
    applyStateToDom(data, false);
    showToast(`Sent a test message to ${camera}`);
  }
}

// Announcements & Alerts: an on-screen notification on Latter Devices, or a spoken broadcast on speakers.
let ANNOUNCE_MODE = "notify";

function setAnnounceMode(mode) {
  ANNOUNCE_MODE = mode === "broadcast" ? "broadcast" : "notify";
  doc.querySelectorAll("#card-announce .segmented [role=radio]").forEach(b =>
    b.setAttribute("aria-checked", String(b.dataset.mode === ANNOUNCE_MODE)));
  doc.querySelectorAll("#card-announce .announce-notify-only").forEach(el => el.classList.toggle("hidden", ANNOUNCE_MODE !== "notify"));
  doc.querySelectorAll("#card-announce .announce-broadcast-only").forEach(el => el.classList.toggle("hidden", ANNOUNCE_MODE !== "broadcast"));
  renderAnnounceTargets();
}

function renderAnnounceTargets() {
  const sel = doc.getElementById("announce-target");
  if (!sel) return;
  const prev = sel.value;
  const displays = (STATE?.system_devices || []).filter(d => d.kind !== "ble_tag" && d.has_display);
  const opts = ANNOUNCE_MODE === "notify"
    ? [{value: "all", label: `All Devices (${displays.length})`}, {value: "occupied_areas", label: "Devices in occupied Areas"}]
        .concat(displays.map(d => ({value: d.device_slug, label: d.title})))
    : [{value: "all", label: "Every speaker"}, {value: "occupied_areas", label: "Speakers in occupied Areas"}];
  sel.innerHTML = opts.map(o => `<option value="${esc(o.value)}" ${o.value === prev ? "selected" : ""}>${esc(o.label)}</option>`).join("");
}

async function sendAnnouncement() {
  const data = await callStudioCommand({
    command: "send_announcement",
    mode: ANNOUNCE_MODE,
    target_device: doc.getElementById("announce-target")?.value || "",
    title: doc.getElementById("announce-title")?.value.trim() || "",
    message: doc.getElementById("announce-message")?.value.trim() || "",
    priority: doc.getElementById("announce-priority")?.value || "normal",
    include_camera: Boolean(doc.getElementById("announce-camera")?.checked)
  });
  if (data) {
    applyStateToDom(data, false);
    showToast(ANNOUNCE_MODE === "notify" ? "Notification sent" : "Broadcast sent");
  }
}

function renderNativeControlRow(item, showEntityId=false, readOnlyNote="") {
  const stateText = `${item.state}${item.unit ? ' ' + item.unit : ''}`;
  const idArg = jsArg(item.entity_id);
  const name = esc(item.name);
  let widgetHtml = `<span class="chip">${esc(stateText)}</span>`;
  if (readOnlyNote) {
    // Read-only: Latter owns this entity's state.
  } else if (item.domain === "button") {
    widgetHtml = `<button type="button" class="btn btn-secondary btn-compact" onclick="espAction(${idArg}, 'press')">Run</button>`;
  } else if (item.domain === "update") {
    widgetHtml = item.state === "on"
      ? `<button type="button" class="btn btn-secondary btn-compact" onclick="espAction(${idArg}, 'install')">Install update</button>`
      : `<span class="chip chip-success">Up to date</span><button type="button" class="btn btn-text btn-compact" onclick="espAction(${idArg}, 'check')">Check</button>`;
  } else if (item.domain === "switch" || item.domain === "light" || item.domain === "fan") {
    widgetHtml = `<input type="checkbox" class="switch" role="switch" aria-label="${name}" ${item.state === "on" ? "checked" : ""} onchange="espAction(${idArg}, this.checked ? 'turn_on' : 'turn_off')">`;
  } else if (item.domain === "select" && item.options && item.options.length) {
    const opts = item.options.map(o => `<option value="${esc(o)}" ${o === item.state ? 'selected' : ''}>${esc(o)}</option>`).join("");
    widgetHtml = `<select aria-label="${name}" onchange="espSelect(${idArg}, this.value)">${opts}</select>`;
  } else if (item.domain === "number") {
    const numVal = parseFloat(item.state) || 0;
    widgetHtml = `<input type="range" aria-label="${name}" min="${esc(item.min ?? 0)}" max="${esc(item.max ?? 100)}" step="${esc(item.step ?? 1)}" value="${esc(numVal)}" onchange="espNumber(${idArg}, this.value)"><span class="chip">${esc(stateText)}</span>`;
  }
  const desc = showEntityId ? esc(item.entity_id) : esc(readOnlyNote || "");
  return settingsRowHtml(name, desc, widgetHtml);
}

function getSectionItems(secId) {
  const sections = STATE?.esphome?.sections || [];
  const found = sections.find(s => s.id === secId);
  return found ? (found.items || []) : [];
}

function renderCohesiveDeviceSections() {
  const esp = STATE?.esphome;
  if (!esp) return;
  const sections = esp.sections || [];
  const totalCount = sections.reduce((acc, s) => acc + s.count, 0);
  doc.getElementById("nav-esp-badge").textContent = totalCount;

  const sortByOrder = (items, keywords) => {
    return [...items].sort((a, b) => {
      const aLow = `${a.name} ${a.entity_id}`.toLowerCase();
      const bLow = `${b.name} ${b.entity_id}`.toLowerCase();
      let aIdx = keywords.findIndex(k => aLow.includes(k));
      let bIdx = keywords.findIndex(k => bLow.includes(k));
      if (aIdx === -1) aIdx = 99;
      if (bIdx === -1) bIdx = 99;
      return aIdx !== bIdx ? aIdx - bIdx : aLow.localeCompare(bLow);
    });
  };

  // 1. Split "area" section items into UI items (Default Category / Show All) vs BLE Beacon
  const areaItems = getSectionItems("area");
  const areaUiItems = [];
  const areaBleItems = [];
  areaItems.forEach(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    if (low.includes("category")) areaUiItems.push(it);
    else areaBleItems.push(it);
  });
  const isPresenceBeaconSwitch = (it) => it.domain === "switch"
    && /presence[ _]beacon/.test(`${it.name} ${it.entity_id}`.toLowerCase());
  doc.getElementById("embedded-area-ble").innerHTML = areaBleItems.map(it => isPresenceBeaconSwitch(it)
    ? renderNativeControlRow(it, false, "Follows Track the Area with BLE proxies")
    : renderNativeControlRow(it)).join("");

  // 2. Home screen & Area UI (the dock itself is the Home dock apps setting below)
  const rawHomeItems = getSectionItems("home");
  const homeItems = sortByOrder(rawHomeItems.concat(areaUiItems), [
    "wake greeting", "weather background", "default category", "show all category"
  ]);
  doc.getElementById("embedded-home").innerHTML = homeItems.length
    ? homeItems.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No on-device Home Screen entities exposed.");

  // 3. Display & Appearance: Logical order + Conditional Brightness visibility based on Auto Brightness Mode
  const rawDispItems = getSectionItems("display");
  const abModeItem = rawDispItems.find(it => `${it.name} ${it.entity_id}`.toLowerCase().includes("auto_brightness") || (it.name || "").toLowerCase().includes("auto brightness"));
  const abMode = abModeItem ? String(abModeItem.state) : "Sun Synchronized";

  const isWeatherSimulation = (it) => /condition[ _]simulation/.test(`${it.name} ${it.entity_id}`.toLowerCase());
  const filteredDisp = rawDispItems.filter(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    if (isWeatherSimulation(it)) return false;
    if (abMode === "Disabled") {
      if (low.includes("day brightness") || low.includes("night brightness") || low.includes("start hour")) return false;
    } else if (abMode === "Sun Synchronized") {
      if (low.includes("manual brightness") || low.includes("start hour")) return false;
    } else if (abMode === "Time Schedule") {
      if (low.includes("manual brightness")) return false;
    }
    return true;
  });
  const dispItems = sortByOrder(filteredDisp, [
    "start screen", "clock face", "time format", "color profile",
    "auto brightness", "manual brightness", "day brightness", "night brightness",
    "day start hour", "night start hour"
  ]);
  doc.getElementById("embedded-display").innerHTML = dispItems.map(it => renderNativeControlRow(it)).join("");

  // 4. Sleep & Wake: Filter out diagnostic timer/alarm readouts, hide Screensaver Style if Docked Screensaver is OFF, and order logically
  const rawSleepItems = getSectionItems("sleep");
  const dockedSsItem = rawSleepItems.find(it => `${it.name} ${it.entity_id}`.toLowerCase().includes("docked_screensaver") || (it.name || "").toLowerCase().includes("docked screensaver"));
  const dockedSsOn = !dockedSsItem || dockedSsItem.state === "on";

  const filteredSleep = rawSleepItems.filter(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    if (low.includes("timer_remaining") || low.includes("timer_active") || low.includes("alarm_ringing")) return false;
    if (!dockedSsOn && low.includes("screensaver style")) return false;
    return true;
  });
  const sleepItems = sortByOrder(filteredSleep, [
    "power profile",
    "battery screen timeout", "docked idle timeout", "battery hibernate timeout",
    "stay awake", "pickup to wake", "tap to wake", "docked screensaver",
    "screensaver style", "hold crown"
  ]);
  doc.getElementById("embedded-sleep").innerHTML = sleepItems.length
    ? sleepItems.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No on-device Sleep & Wake entities exposed.");

  const pwrProfItem = rawSleepItems.find(it => `${it.name} ${it.entity_id}`.toLowerCase().includes("power_profile") || (it.name || "").toLowerCase().includes("power profile"));
  const pwrWrap = doc.getElementById("dash-power-profile-wrap");
  const pwrSel = doc.getElementById("dash-power-profile-select");
  if (pwrWrap && pwrSel) {
    if (pwrProfItem && pwrProfItem.options && pwrProfItem.options.length) {
      pwrWrap.classList.remove("hidden");
      pwrSel.dataset.ent = pwrProfItem.entity_id;
      pwrSel.innerHTML = pwrProfItem.options.map(o =>
        `<option value="${esc(o)}" ${o === pwrProfItem.state ? 'selected' : ''}>${esc(o)}</option>`
      ).join("");
    } else {
      pwrWrap.classList.add("hidden");
    }
  }

  // 5. Voice Assistant: Hide Active Wake Word & Sensitivity drawer when Wake Word Mode is Disabled
  const voiceItems = getSectionItems("voice");
  const wwModeItem = voiceItems.find(it => `${it.name} ${it.entity_id}`.toLowerCase().includes("wake_word_mode") || (it.name || "").toLowerCase().includes("wake word mode"));
  const wwDisabled = wwModeItem && wwModeItem.state === "Disabled";

  const voicePrimary = [];
  const voiceSens = [];
  voiceItems.forEach(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    if (low.includes("sensitivity")) {
      voiceSens.push(it);
    } else if (!(wwDisabled && low.includes("active wake word"))) {
      voicePrimary.push(it);
    }
  });
  const sortedVoicePrimary = sortByOrder(voicePrimary, [
    "wake word mode", "active wake word", "visual profile", "wake screen"
  ]);
  doc.getElementById("embedded-voice-primary").innerHTML = sortedVoicePrimary.length
    ? sortedVoicePrimary.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No on-device Voice Assistant entities exposed.");
  doc.getElementById("embedded-voice-sens").innerHTML = voiceSens.length
    ? voiceSens.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No per-model sensitivity controls exposed.");
  const sensDetails = doc.getElementById("details-voice-sens");
  if (sensDetails) {
    sensDetails.classList.toggle("hidden", !!(wwDisabled || voiceSens.length === 0));
  }

  // 6. Sound & Media: Split player appearance/shortcuts vs Library Sorting drawer
  const soundItems = sortByOrder(getSectionItems("sound"), [
    "alert volume", "volume step", "game sound"
  ]);
  doc.getElementById("embedded-sound").innerHTML = soundItems.map(it => renderNativeControlRow(it)).join("");

  const allMusicItems = getSectionItems("music").filter(it => it.domain !== "media_player");
  const musicPrimary = [];
  const musicSort = [];
  allMusicItems.forEach(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    if (low.includes("sort")) musicSort.push(it);
    else musicPrimary.push(it);
  });
  doc.getElementById("embedded-music").innerHTML = sortByOrder(musicPrimary, [
    "album art style", "overlay style", "speaker shortcut", "library shortcut"
  ]).map(it => renderNativeControlRow(it)).join("");
  const sortBox = doc.getElementById("embedded-music-sort");
  if (sortBox) {
    sortBox.innerHTML = musicSort.map(it => renderNativeControlRow(it)).join("");
  }

  // Render Quick Actions right at the top of Device Overview!
  const actionItems = getSectionItems("actions");
  const qaBox = doc.getElementById("dash-quick-actions");
  if (qaBox) {
    qaBox.innerHTML = actionItems.length
      ? actionItems.map(it =>
          `<button type="button" class="btn btn-secondary" onclick="espAction(${jsArg(it.entity_id)}, 'press')">${esc(it.name)}</button>`
        ).join("")
      : emptyStateHtml("This Device has no quick actions.");
  }

  const batItems = getSectionItems("battery");
  doc.getElementById("embedded-battery").innerHTML = batItems.length
    ? batItems.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No battery telemetry entities reported.");

  const isDeveloperItem = (it) => /(telemetry[ _]profiler|ram[ _]low[ _]water|ram[ _]largest[ _]block|psram[ _]low[ _]water|condition[ _]simulation)/
    .test(`${it.name} ${it.entity_id}`.toLowerCase());
  const diagItems = getSectionItems("network").concat(rawDispItems.filter(isWeatherSimulation));
  const netItems = diagItems.filter(it => !isDeveloperItem(it));
  const devItems = diagItems.filter(isDeveloperItem);
  doc.getElementById("embedded-network").innerHTML = netItems.length
    ? netItems.map(it => renderNativeControlRow(it)).join("")
    : emptyStateHtml("No network or diagnostic entities reported.");
  doc.getElementById("embedded-developer").innerHTML = devItems.map(it => renderNativeControlRow(it)).join("");
  doc.getElementById("details-developer")?.classList.toggle("hidden", !devItems.length);

  // Only show the extra "Device Sensors & Controls" card on Overview if the device has "other" entities or is a sensor/headless node
  const otherItems = getSectionItems("other");
  const sensorCard = doc.getElementById("dash-sensor-entities-card");
  const dashBox = doc.getElementById("dash-device-entities");
  if (sensorCard && dashBox) {
    if (otherItems.length > 0) {
      sensorCard.classList.remove("hidden");
      dashBox.innerHTML = otherItems.map(it => renderNativeControlRow(it, false)).join("");
    } else {
      sensorCard.classList.add("hidden");
    }
  }

  renderRawEntityList();
}

function renderRawEntityList() {
  const esp = STATE?.esphome;
  if (!esp || !esp.sections) return;
  const query = (doc.getElementById("esp-search")?.value || "").trim().toLowerCase();
  let allItems = [];
  esp.sections.forEach(s => { allItems = allItems.concat(s.items || []); });
  if (query) {
    allItems = allItems.filter(it =>
      it.name.toLowerCase().includes(query) || it.entity_id.toLowerCase().includes(query)
    );
  }
  const box = doc.getElementById("raw-entity-items");
  if (box) {
    box.innerHTML = allItems.map(it => renderNativeControlRow(it, true)).join("");
  }
}

function renderWallpaperGallery(wallpapers, slug, shape) {
  const box = doc.getElementById("wp-gallery-grid");
  if (!box) return;
  const shapeClass = shape === "square" ? "square" : "circle";
  const items = wallpapers || [];
  box.innerHTML = items.length ? items.map(wp => {
    const idArg = jsArg(wp.id);
    return `<div class="wp-card ${wp.active ? 'active' : ''}">
      <img class="wp-thumb ${shapeClass}" src="${esc(wp.thumb_url || "")}" loading="lazy" alt="${esc(wp.name)}">
      <div class="wp-title">${esc(wp.name)}</div>
      <div class="wp-actions">
        ${wp.active ? '<span class="chip chip-primary">Active</span>' : `<button type="button" class="btn btn-secondary btn-compact" onclick="selectWallpaperSource(${idArg})">Use</button>`}
        <button type="button" class="btn btn-text btn-compact" aria-pressed="${!!wp.favorite}" aria-label="${wp.favorite ? 'Remove from favorites' : 'Add to favorites'}" onclick="toggleWallpaperFav(${idArg})">${wp.favorite ? '★' : '☆'}</button>
        ${wp.deletable ? iconButtonHtml(ICON_DELETE, `Delete ${wp.name}`, `deleteWallpaper(${idArg})`, "danger") : ''}
      </div>
    </div>`;
  }).join("") : emptyStateHtml("No wallpapers available.");
}

async function uploadWallpaperFile() {
  const input = doc.getElementById("wp-file-input");
  if (!input.files || !input.files.length) {
    showToast("Failed: select an image file first", "error");
    return;
  }
  const file = input.files[0];
  const reader = new FileReader();
  reader.onload = async () => {
    const data = await callStudioCommand({
        command: "upload_wallpaper",
        filename: file.name,
        data_b64: reader.result
      });
  if (data) {
      input.value = "";
      applyStateToDom(data, true);
      showToast("Wallpaper uploaded & activated");
    }
  };
  reader.readAsDataURL(file);
}

async function selectWallpaperSource(sourceId) {
  const data = await callStudioCommand({command: "select_wallpaper", source_id: sourceId});
  if (data) {
    applyStateToDom(data, false);
    showToast(sourceId ? "Wallpaper activated" : "Wallpaper cleared");
  }
}

async function toggleWallpaperFav(sourceId) {
  const data = await callStudioCommand({command: "toggle_wallpaper_favorite", source_id: sourceId});
  if (data) {
    applyStateToDom(data, false);
    showToast("Updated wallpaper favorites");
  }
}

async function deleteWallpaper(sourceId) {
  const data = await callStudioCommand({command: "delete_wallpaper", source_id: sourceId});
  if (data) {
    applyStateToDom(data, false);
    showToast("Deleted wallpaper");
  }
}

async function espAction(entity_id, action) {
  const data = await callStudioCommand({command: "esphome_entity_action", entity_id, action});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Executed ${action} on ${entity_id}`);
  }
}

async function espSelect(entity_id, option) {
  const data = await callStudioCommand({command: "esphome_entity_action", entity_id, option});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Selected ${option}`);
  }
}

async function espNumber(entity_id, level) {
  const data = await callStudioCommand({command: "esphome_entity_action", entity_id, level});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Updated ${entity_id} = ${level}`);
  }
}

function renumberCameraRows() {
  const rows = doc.querySelectorAll("#cameras-list .camera-row-item");
  rows.forEach((row, idx) => {
    const lbl = row.querySelector(".cam-slot-lbl");
    if (lbl) {
      lbl.textContent = idx === 0
        ? "Camera 1 (Primary / Default Notification Camera)"
        : `Camera ${idx + 1}`;
    }
  });
}

function addCameraRow(entityId="") {
  const list = doc.getElementById("cameras-list");
  if (!list) return;
  const existingCount = list.querySelectorAll(".camera-row-item").length;
  if (existingCount >= 10) {
    showToast("Failed: a System can have up to 10 cameras", "error");
    return;
  }
  const row = document.createElement("div");
  row.className = "list-row camera-row-item";
  const camOptions = (STATE?.catalog?.cameras || []).map(c =>
    `<option value="${esc(c.id)}" ${c.id === entityId ? 'selected' : ''}>${esc(c.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div class="stacked-field list-row-grow">
      <span class="field-label cam-slot-lbl"></span>
      <select class="cam-ent-sel" aria-label="Camera" onchange="saveSetting('system', 'camera_entities')"><option value="">— Choose a camera —</option>${camOptions}</select>
    </div>
    <button type="button" class="btn btn-text btn-compact" onclick="renderCameraPreview(this.parentElement.querySelector('.cam-ent-sel').value)">Preview</button>
    ${iconButtonHtml(ICON_DELETE, "Remove camera", "this.parentElement.remove(); renumberCameraRows(); saveSetting('system', 'camera_entities');", "danger")}
  `;
  list.appendChild(row);
  renumberCameraRows();
}

function addCalendarRow(entityId="") {
  const list = doc.getElementById("calendars-list");
  if (!list) return;
  const row = document.createElement("div");
  row.className = "list-row calendar-row-item";
  const calOptions = (STATE?.catalog?.calendars || []).map(c =>
    `<option value="${esc(c.id)}" ${c.id === entityId ? 'selected' : ''}>${esc(c.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div class="stacked-field list-row-grow">
      <select class="cal-ent-sel" aria-label="Calendar" onchange="saveSetting('system', 'calendar_entities')"><option value="">— Choose a calendar —</option>${calOptions}</select>
    </div>
    ${iconButtonHtml(ICON_DELETE, "Remove calendar", "this.parentElement.remove(); saveSetting('system', 'calendar_entities');", "danger")}
  `;
  list.appendChild(row);
}

let REMOTE_GROUPS_STATE = [];

function getInventoryRemoteIds() {
  const out = [];
  doc.querySelectorAll("#remotes-list .rem-ent-sel").forEach(sel => {
    const v = (sel.value || "").trim();
    if (v && !out.includes(v)) out.push(v);
  });
  return out;
}

function getRemoteFriendlyLabel(entId) {
  const cat = STATE?.catalog?.remotes || [];
  const found = cat.find(r => r.id === entId);
  return found ? found.name.split(" (")[0] : entId;
}

function renderRemoteGroupsEditor() {
  const box = doc.getElementById("remote-groups-list");
  if (!box) return;
  const areas = STATE?.catalog?.areas || [];
  const invIds = getInventoryRemoteIds();
  if (!REMOTE_GROUPS_STATE.length) {
    box.innerHTML = emptyStateHtml("No remote groups yet.");
  } else {
    box.innerHTML = REMOTE_GROUPS_STATE.map((grp, gIdx) => {
      const areaOpts = [`<option value="">No Area (assign to Devices only)</option>`].concat(
        areas.map(a => `<option value="${esc(a.id)}" ${a.id === grp.area_id ? 'selected' : ''}>${esc(a.name)}</option>`)
      ).join("");
      const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
      const pool = selectedRems.filter(id => invIds.includes(id)).concat(invIds.filter(id => !selectedRems.includes(id)));
      const pills = pool.length
        ? pool.map(entId => {
            const pos = selectedRems.indexOf(entId);
            const isEn = pos >= 0;
            const badge = isEn ? (pos === 0 ? "★ Primary: " : `#${pos + 1}: `) : "+ ";
            return `<button type="button" class="pill ${isEn ? 'enabled' : ''}" aria-pressed="${isEn}" onclick="toggleRemoteInGroup(${gIdx}, ${jsArg(entId)})">${esc(badge)}${esc(getRemoteFriendlyLabel(entId))}</button>`;
          }).join("")
        : `<span class="help-text">Add remotes to the remote inventory first.</span>`;
      return `<div class="list-block">
        <div class="list-row-head">
          <div class="list-row-main">
            <div class="stacked-field"><label>Group name</label><input type="text" aria-label="Group name" value="${esc(grp.name || '')}" placeholder="e.g. TV wall" onchange="updateRemoteGroupField(${gIdx}, 'name', this.value)" onkeydown="if (event.key === 'Enter') this.blur()"></div>
            <div class="stacked-field"><label>Area (loads when a Device enters it)</label><select aria-label="Area" onchange="updateRemoteGroupField(${gIdx}, 'area_id', this.value)">${areaOpts}</select></div>
          </div>
          ${iconButtonHtml(ICON_DELETE, `Delete remote group ${grp.name || ""}`, `removeRemoteGroupRow(${gIdx})`, "danger")}
        </div>
        <div class="stacked-field"><span class="field-label">Remotes (the first one selected is the primary power target)</span><div class="pill-list">${pills}</div></div>
      </div>`;
    }).join("");
  }
  renderDeviceRemoteAssignments();
}

function addRemoteGroupRow() {
  const idx = REMOTE_GROUPS_STATE.length + 1;
  REMOTE_GROUPS_STATE.push({
    id: `rg_${Date.now()}_${idx}`,
    name: `Area group ${idx}`,
    area_id: "",
    remotes: []
  });
  renderRemoteGroupsEditor();
  saveSetting("system", "remote_groups");
}

function removeRemoteGroupRow(gIdx) {
  REMOTE_GROUPS_STATE.splice(gIdx, 1);
  saveSetting("system", "remote_groups");
  renderRemoteGroupsEditor();
}

function updateRemoteGroupField(gIdx, field, val) {
  if (!REMOTE_GROUPS_STATE[gIdx]) return;
  REMOTE_GROUPS_STATE[gIdx][field] = val;
  saveSetting("system", "remote_groups");
  if (field === "name") renderDeviceRemoteAssignments();
}

function toggleRemoteInGroup(gIdx, entId) {
  const grp = REMOTE_GROUPS_STATE[gIdx];
  if (!grp) return;
  grp.remotes = Array.isArray(grp.remotes) ? grp.remotes : [];
  if (grp.remotes.includes(entId)) {
    grp.remotes = grp.remotes.filter(x => x !== entId);
  } else {
    grp.remotes.push(entId);
  }
  saveSetting("system", "remote_groups");
  renderRemoteGroupsEditor();
}

function renderDeviceRemoteAssignments() {
  const box = doc.getElementById("device-remote-assignments-list");
  if (!box) return;
  const devs = (STATE?.system_devices || []).filter(d => d.kind !== "ble_tag" && d.has_display);
  if (!devs.length) {
    box.innerHTML = emptyStateHtml("No Latter displays yet.");
    return;
  }
  const savedGroups = STATE?.system_config?.remote_groups || [];
  box.innerHTML = devs.map(d => {
    const curMode = d.device_remote_group || "area_auto";
    const opts = [
      `<option value="area_auto" ${curMode === 'area_auto' ? 'selected' : ''}>Follow the active Area</option>`,
      ...savedGroups.map(g => `<option value="${esc('group:' + g.id)}" ${curMode === ('group:' + g.id) ? 'selected' : ''}>Group: ${esc(g.name)}</option>`),
      `<option value="all" ${curMode === 'all' ? 'selected' : ''}>All System remotes</option>`
    ].join("");
    return settingsRowHtml(
      esc(d.title),
      esc(`Active Area: ${d.active_area_name || "—"}`),
      `<select aria-label="Remotes for ${esc(d.title)}" onchange="assignDeviceRemoteGroup(${jsArg(d.subentry_id)}, ${jsArg(d.title)}, this.value)">${opts}</select>`
    );
  }).join("");
}

async function assignDeviceRemoteGroup(subentryId, title, modeVal) {
  const data = await callStudioCommand({command: "set_device_remote_group", subentry_id: subentryId, device_remote_group: modeVal});
  if (data) {
    applyStateToDom(data, false);
    showToast(`Updated remote assignment for ${title}`);
  }
}

function renumberRemoteControlRows() {
  const rows = doc.querySelectorAll("#remotes-list .remote-row-item");
  rows.forEach((row, idx) => {
    const lbl = row.querySelector(".rem-slot-lbl");
    if (lbl) {
      lbl.textContent = idx === 0
        ? "Slot 1 (Primary Power Target)"
        : `Slot ${idx + 1}`;
    }
  });
}

function addRemoteControlRow(entityId="") {
  const list = doc.getElementById("remotes-list");
  if (!list) return;
  const existingCount = list.querySelectorAll(".remote-row-item").length;
  if (existingCount >= 10) {
    showToast("Failed: a System can have up to 10 remotes", "error");
    return;
  }
  const row = document.createElement("div");
  row.className = "list-row remote-row-item";
  const remOptions = (STATE?.catalog?.remotes || []).map(r =>
    `<option value="${esc(r.id)}" ${r.id === entityId ? 'selected' : ''}>${esc(r.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div class="stacked-field list-row-grow">
      <span class="field-label rem-slot-lbl"></span>
      <select class="rem-ent-sel" aria-label="Remote or media player" onchange="saveSetting('system', 'remotes_list'); renderRemoteGroupsEditor();"><option value="">— Choose a remote or media player —</option>${remOptions}</select>
    </div>
    ${iconButtonHtml(ICON_DELETE, "Remove remote", "this.parentElement.remove(); renumberRemoteControlRows(); saveSetting('system', 'remotes_list'); renderRemoteGroupsEditor();", "danger")}
  `;
  list.appendChild(row);
  renumberRemoteControlRows();
}

function addVolumeOverrideRow(speaker="", target="") {
  const list = doc.getElementById("volume-overrides-list");
  if (!list) return;
  if (list.querySelectorAll(".vol-override-row").length >= 10) {
    showToast("Failed: a System can have up to 10 volume overrides", "error");
    return;
  }
  const row = document.createElement("div");
  row.className = "list-row vol-override-row";
  const spkOptions = (STATE?.catalog?.ma_speakers || []).map(s =>
    `<option value="${esc(s.id)}" ${s.id === speaker ? 'selected' : ''}>${esc(s.name)}</option>`
  ).join("");
  const tgtOptions = (STATE?.catalog?.volume_targets || []).map(t =>
    `<option value="${esc(t.id)}" ${t.id === target ? 'selected' : ''}>${esc(t.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div class="list-row-main">
      <div class="stacked-field"><span class="field-label">When audio plays on</span><select class="vo-spk" aria-label="Speaker" onchange="saveSetting('system', 'volume_overrides')"><option value="">— Choose a speaker —</option>${spkOptions}</select></div>
      <div class="stacked-field"><span class="field-label">Change the volume on</span><select class="vo-tgt" aria-label="Volume target" onchange="saveSetting('system', 'volume_overrides')"><option value="">— Choose a volume target —</option>${tgtOptions}</select></div>
    </div>
    ${iconButtonHtml(ICON_DELETE, "Remove volume override", "this.parentElement.remove(); saveSetting('system', 'volume_overrides');", "danger")}
  `;
  list.appendChild(row);
}


function copyToClipboard(text, successMsg) {
  if (!text) return;
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    navigator.clipboard.writeText(text).then(() => {
      showToast(successMsg);
    }).catch(() => {
      fallbackCopyText(text, successMsg);
    });
  } else {
    fallbackCopyText(text, successMsg);
  }
}

function fallbackCopyText(text, successMsg) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.className = "offscreen";
    doc.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    doc.body.removeChild(ta);
    showToast(ok ? successMsg : "Failed: select the text and copy it manually", ok ? "info" : "error");
  } catch (_e) {
    showToast("Failed: select the text and copy it manually", "error");
  }
}


function copyTextById(elId) {
  const text = doc.getElementById(elId)?.textContent || "";
  copyToClipboard(text, "Copied to clipboard");
}

let pendingRemoveEntryId = "";
let pendingRemoveTitle = "";

function closeRemoveDeviceModal() {
  closeDialog("latter-rm-modal");
  pendingRemoveEntryId = "";
  pendingRemoveTitle = "";
}

function removeManagedDevice(entryId, title) {
  pendingRemoveEntryId = entryId;
  pendingRemoveTitle = title || entryId;
  const desc = doc.getElementById("latter-rm-desc");
  if (desc) {
    desc.textContent = `Remove '${pendingRemoveTitle}' from Latter? Your ESPHome device stays in Home Assistant, and you can add it again anytime.`;
  }
  openDialog("latter-rm-modal");
}

function updateResetDeviceConfirm() {
  const dev = doc.getElementById("latter-reset-device-settings");
  const opts = doc.getElementById("latter-reset-latter-options");
  const btn = doc.getElementById("latter-reset-confirm-btn");
  if (btn) btn.disabled = !((dev && dev.checked && !dev.disabled) || (opts && opts.checked));
}

function openResetDeviceModal() {
  if (!ACTIVE_SUBENTRY_ID) {
    showToast("Failed: select a Device first", "error");
    return;
  }
  const isBleTag = STATE?.config?.kind === "ble_tag";
  const dev = doc.getElementById("latter-reset-device-settings");
  const opts = doc.getElementById("latter-reset-latter-options");
  if (dev) {
    dev.checked = !isBleTag;
    dev.disabled = isBleTag;
  }
  if (opts) opts.checked = true;
  const title = doc.getElementById("latter-reset-title");
  if (title) title.textContent = `Reset '${STATE?.title || "this Device"}' to defaults?`;
  updateResetDeviceConfirm();
  openDialog("latter-reset-modal");
}

function closeResetDeviceModal() {
  closeDialog("latter-reset-modal");
}

async function confirmResetDevice() {
  const dev = doc.getElementById("latter-reset-device-settings");
  const opts = doc.getElementById("latter-reset-latter-options");
  const deviceSettings = !!(dev && dev.checked && !dev.disabled);
  const latterOptions = !!(opts && opts.checked);
  closeResetDeviceModal();
  if (!HASS_REF || !ACTIVE_SUBENTRY_ID || (!deviceSettings && !latterOptions)) return;
  const data = await callStudioWS({
    type: "latter/device/reset",
    subentry_id: ACTIVE_SUBENTRY_ID,
    device_settings: deviceSettings,
    latter_options: latterOptions
  });
  if (data) {
    applyStateToDom(data, {system: false, device: true});
    showToast(deviceSettings ? "Reset sent; the device is restarting" : "Latter options reset to defaults");
  }
}

async function confirmRemoveManagedDevice() {
  const entryId = pendingRemoveEntryId;
  const title = pendingRemoveTitle;
  closeRemoveDeviceModal();
  if (!entryId) return;
  const data = await callStudioCommand({command: "remove_device", subentry_id: entryId});
  if (data) {
    const removedSelected = data.removed && data.removed_subentry_id === ACTIVE_SUBENTRY_ID;
    if (removedSelected) {
      ACTIVE_SUBENTRY_ID = "";
      DEVICE_SELECTED = false;
      setScope("device", "select_device_prompt");
    }
    applyStateToDom(data, false);
    showToast(`Removed '${title}' from Latter`);
    if (removedSelected && HOST_ELEMENT && typeof HOST_ELEMENT._resubscribe === "function") {
      await HOST_ELEMENT._resubscribe(false);
    }
  }
}

function onSelectBleCandidate(targetAddr) {
  if (!targetAddr) return;
  const cands = STATE?.discovered_ble_devices || [];
  const found = cands.find(c => c.target_address === targetAddr);
  const nameInp = doc.getElementById("ble-custom-name");
  const addrInp = doc.getElementById("ble-custom-addr");
  if (addrInp) addrInp.value = targetAddr;
  if (nameInp && found) nameInp.value = found.title;
}

function openAddDeviceModal() {
  const bleCands = STATE?.discovered_ble_devices || [];
  const blePicker = doc.getElementById("ble-candidate-picker");
  if (blePicker) {
    blePicker.innerHTML = [`<option value="">— Choose a discovered device, or enter one below —</option>`].concat(
      bleCands.map(c => `<option value="${esc(c.target_address)}">${esc(c.label)}</option>`)
    ).join("");
  }
  const nameInp = doc.getElementById("ble-custom-name");
  const addrInp = doc.getElementById("ble-custom-addr");
  if (nameInp) nameInp.value = "";
  if (addrInp) addrInp.value = "";
  populateSelect("ble-custom-person", STATE?.catalog?.persons || [], "", true);
  openDialog("latter-add-dev-modal");
}

function closeAddDeviceModal() {
  closeDialog("latter-add-dev-modal");
}

async function confirmAddDeviceModal() {
  const name = doc.getElementById("ble-custom-name")?.value?.trim() || "";
  const target_address = doc.getElementById("ble-custom-addr")?.value?.trim() || "";
  const assigned_person = doc.getElementById("ble-custom-person")?.value || "";
  if (!name || !target_address) {
    showToast("Enter a name and a BLE address or entity", "error");
    return;
  }
  closeAddDeviceModal();
  const data = await callStudioCommand({
    command: "add_ble_device",
    name,
    target_address,
    assigned_person
  });
  if (data) {
    applyStateToDom(data, false);
    showToast(`Added BLE device '${name}'`);
  }
}

function onAssignedPersonChanged(personEnt) {
  saveSetting("device", "assigned_person");
}

function toggleDeviceTableSort(col) {
  if (DEVICE_SORT_COL === col) {
    DEVICE_SORT_ASC = !DEVICE_SORT_ASC;
  } else {
    DEVICE_SORT_COL = col;
    DEVICE_SORT_ASC = true;
  }
  if (STATE) {
    renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config);
  }
}

function onFilterDeviceCategory(val) {
  DEVICE_CATEGORY_FILTER = val || "all";
  if (STATE) {
    renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config);
  }
}

async function createDeviceGroup() {
  const nameEl = doc.getElementById("new-group-name");
  const descEl = doc.getElementById("new-group-desc");
  const name = (nameEl?.value || "").trim();
  if (!name) {
    showToast("Enter a group name first");
    return;
  }
  const data = await callStudioCommand({command: "create_device_group", name, description: (descEl?.value || "").trim()});
  if (data) {
    if (nameEl) nameEl.value = "";
    if (descEl) descEl.value = "";
    applyStateToDom(data, false);
    showToast(`Created device group '${name}'`);
  }
}

async function deleteDeviceGroup(groupId) {
  const data = await callStudioCommand({command: "delete_device_group", group_id: groupId});
  if (data) {
    applyStateToDom(data, false);
    showToast("Removed device group");
  }
}

async function captureDeviceProfile() {
  const subentryId = doc.getElementById("profile-source-device")?.value || "";
  const source = (STATE?.system_devices || []).find(d => d.subentry_id === subentryId);
  if (!source) {
    showToast("Failed: choose the Device to capture from", "error");
    return;
  }
  const nameEl = doc.getElementById("new-profile-name");
  const descEl = doc.getElementById("new-profile-desc");
  const name = (nameEl?.value || "").trim() || `${source.title} Profile`;
  const data = await callStudioCommand({command: "capture_profile", subentry_id: subentryId, name, description: (descEl?.value || "").trim()});
  if (data) {
    if (nameEl) nameEl.value = "";
    if (descEl) descEl.value = "";
    applyStateToDom(data, false);
    showToast(`Saved profile '${name}'`);
  }
}

async function applySavedProfile(profileId) {
  const scopeSel = doc.getElementById("profile-target-scope");
  const scope = scopeSel?.value || "";
  if (!scope) {
    showToast("Failed: choose where to apply the profile", "error");
    return;
  }
  const data = await callStudioCommand({command: "apply_profile", profile_id: profileId, target_scope: scope});
  if (data) {
    applyStateToDom(data, {system: false, device: true});
    showToast(`Applied the profile to ${scopeSel?.selectedOptions?.[0]?.textContent || scope}`);
  }
}

async function deleteSavedProfile(profileId) {
  const data = await callStudioCommand({command: "delete_profile", profile_id: profileId});
  if (data) {
    applyStateToDom(data, false);
    showToast("Deleted profile");
  }
}

function triggerJsonDownload(bundle) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const slugPart = bundle.scope === "system" ? "system" : `device-${bundle.target_device || 'esphome'}`;
  const filename = `latter-${slugPart}-backup-${dateStr}.json`;
  const blob = new Blob([JSON.stringify(bundle, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  doc.body.appendChild(a);
  a.click();
  setTimeout(() => {
    doc.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}

async function exportBackupToComputer(overrideScope) {
  const choice = overrideScope === "device"
    ? `device:${ACTIVE_SUBENTRY_ID}`
    : (doc.getElementById("bkp-scope-select")?.value || "system");
  const deviceId = choice.startsWith("device:") ? choice.slice("device:".length) : "";
  if (choice.startsWith("device:") && !deviceId) {
    showToast("Failed: choose a Device", "error");
    return;
  }
  const data = await callStudioWS(deviceId
    ? {type: "latter/device/export", subentry_id: deviceId}
    : {type: "latter/system/export"});
  if (data && data.bundle) {
    triggerJsonDownload(data.bundle);
    showToast(deviceId ? "Downloaded the Device backup" : "Downloaded the System backup");
  }
}

function restoreFromUploadedFile() {
  const input = doc.getElementById("bkp-upload-file");
  if (!input || !input.files || !input.files.length) {
    showToast("Choose a .JSON backup file first");
    return;
  }
  const restoreEsp = doc.getElementById("bkp-restore-esp")?.checked ?? true;
  const file = input.files[0];
  const reader = new FileReader();
  reader.onload = async () => {
    let bundle;
    try {
      const parsed = JSON.parse(reader.result);
      bundle = parsed.bundle || parsed;
    } catch (_e) {
      showToast("Failed: that file isn't a Latter backup (.JSON)", "error");
      return;
    }
    let msg;
    if (bundle.scope === "device") {
      const targetId = doc.getElementById("bkp-restore-device")?.value || "";
      if (!targetId) {
        showToast("Failed: choose the Device to restore this Device backup onto", "error");
        return;
      }
      msg = {type: "latter/device/import", subentry_id: targetId, bundle, restore_esphome_entities: restoreEsp};
    } else {
      msg = {type: "latter/system/import", bundle, restore_esphome_entities: restoreEsp};
      if (ACTIVE_SUBENTRY_ID) msg.subentry_id = ACTIVE_SUBENTRY_ID;
    }
    const data = await callStudioWS(msg);
    if (data) {
      input.value = "";
      applyStateToDom(data, true);
      showToast(bundle.scope === "device" ? "Restored the Device backup" : "Restored the System backup");
    }
  };
  reader.readAsText(file);
}

function applyStateToDom(data, forceFormUpdate=false) {
  // Live pushes and command answers leave out the entity catalog unless a registry changed; keep the last one.
  if (!data.catalog && STATE?.catalog) data.catalog = STATE.catalog;
  STATE = data;
  doc.getElementById("studio-root")?.classList.remove("is-loading");
  doc.getElementById("studio-load-error")?.classList.add("hidden");
  const cfg = data.config || {};
  const live = data.live || {};
  const esp = data.esphome;

  const areaName = live.active_area_name || "—";
  const caps = data.capabilities || {};
  updateTopHeaderForScope();

  // Capability-Aware Device Sidebar Tabs
  const showDisplay = !!caps.has_display;
  const showPower = !!caps.has_power;
  const showAudioVoice = !!(caps.has_voice || caps.has_audio);
  doc.getElementById("nav-btn-home_display")?.classList.toggle("hidden", !showDisplay);
  doc.getElementById("nav-btn-audio_voice")?.classList.toggle("hidden", !showAudioVoice);
  doc.getElementById("nav-btn-power")?.classList.toggle("hidden", !showPower);

  // Live Battery, Wi-Fi/BLE & IP/Target from the current Device's System entry. Unknown renders as "—".
  const curDevEntry = (data.system_devices || []).find(d => d.is_current) || {};
  const isBleOnly = cfg.kind === "ble_tag";
  const winBleRow = (live.ble_survey_rows || []).find(r => r.is_winner);
  let batText = "—";
  if (!isBleOnly && curDevEntry.battery_level !== null && curDevEntry.battery_level !== undefined) {
    if (curDevEntry.is_charging) {
      batText = `${fmtPercent(curDevEntry.battery_level)} (charging)`;
    } else if (curDevEntry.is_usb_connected) {
      batText = `${fmtPercent(curDevEntry.battery_level)} (plugged in)`;
    } else {
      batText = fmtPercent(curDevEntry.battery_level);
    }
  }
  let wifiText = "—";
  if (curDevEntry.wifi_rssi !== null && curDevEntry.wifi_rssi !== undefined) {
    wifiText = `${fmtNumber(curDevEntry.wifi_rssi)} dBm`;
  } else if (isBleOnly && winBleRow && winBleRow.effective_rssi !== null) {
    wifiText = `${fmtNumber(winBleRow.effective_rssi)} dBm (BLE)`;
  }
  const ipStr = curDevEntry.ip_address || (isBleOnly ? (cfg.ble_target_address || "—") : "—");

  const hasAssignedArea = !!curDevEntry.has_assigned_area;
  const isRoaming = !hasAssignedArea;
  const areaLblEl = doc.getElementById("st-area-label");
  if (areaLblEl) areaLblEl.textContent = hasAssignedArea ? "Area" : "Current Area";

  // Overview stats and the Now card. Unknown renders as "—".
  const rawDevSw = String(live.device_sw_version || esp?.device?.sw_version || "").replace(/^v/i, "");
  doc.getElementById("st-area").textContent = hasAssignedArea ? (curDevEntry.area_label || areaName) : areaName;
  const now = live.now || {};
  doc.getElementById("now-speaker").textContent = now.speaker_name || "—";
  const playing = [now.media_title, now.media_artist].filter(Boolean).join(" — ");
  doc.getElementById("now-playing").textContent = playing
    ? (now.media_state === "paused" ? `${playing} (paused)` : playing)
    : (now.media_state ? "Nothing playing" : "—");
  renderDeviceHealth();
  renderSystemIssues();
  const links = data.links || {};
  doc.getElementById("row-open-in-ha")?.classList.toggle("hidden", !links.esphome_device_id);
  doc.getElementById("row-diagnostics")?.classList.toggle("hidden", !links.latter_device_id);
  doc.getElementById("row-replace-hardware")?.classList.toggle("hidden", isBleOnly);
  doc.getElementById("st-battery").textContent = batText;
  doc.getElementById("st-wifi").textContent = wifiText;
  const fwEl = doc.getElementById("st-fw-version");
  if (fwEl) {
    fwEl.textContent = rawDevSw
      ? (live.fw_update_available ? `v${rawDevSw} (update available)` : `v${rawDevSw}`)
      : "—";
  }

  const grpList = data.device_groups || [];
  const grpObj = grpList.find(g => g.id === cfg.device_group);
  doc.getElementById("st-group").textContent = grpObj ? grpObj.name : (cfg.device_group || "—");

  doc.getElementById("dash-hw-model").textContent = curDevEntry.model_label || esp?.device?.model || "—";
  doc.getElementById("dash-ip-addr").textContent = ipStr;
  doc.getElementById("dash-ble-mode").textContent = `${isRoaming ? "Roaming" : "Stationary"}${live.active_area_name ? ` • ${live.active_area_name}` : ""}`;
  const winRow = (live.ble_survey_rows || []).find(r => r.is_winner);
  const distSuffix = (live.ble_closest_proxy && winRow && winRow.distance_m != null) ? ` (~${fmtDistance(winRow.distance_m)})` : "";
  doc.getElementById("dash-ble-proxy").textContent = (live.ble_closest_proxy || "—") + distSuffix;
  const proxyRow = doc.getElementById("dash-row-ble-proxy");
  if (proxyRow) proxyRow.classList.toggle("hidden", !(caps.has_ble_beacon && cfg.native_ble_tracking));

  renderLogsView();
  renderActiveSurveyDeviceBars();
  renderWallpaperGallery(data.wallpapers, cfg.device_slug, cfg.display_shape);
  const activeEl = getStudioActiveElement();
  if (!activeEl || !["SELECT", "INPUT"].includes(activeEl.tagName)) {
    renderCohesiveDeviceSections();
    renderSystemOverview(data.system_devices, data.system_controls, cfg);
  }

  // Forms: `true` reloads both scopes; {system, device} reloads only the named scopes, so a save of one
  // scope (or a Device switch) never discards unsaved edits in the other.
  let reload = {system: false, device: false};
  if (!INITIAL_FORM_LOADED || forceFormUpdate === true) {
    reload = {system: true, device: true};
  } else if (forceFormUpdate && typeof forceFormUpdate === "object") {
    reload = {system: !!forceFormUpdate.system, device: !!forceFormUpdate.device};
  }
  if (reload.system || reload.device) {
    INITIAL_FORM_LOADED = true;
    renderCohesiveDeviceSections();
    renderSystemOverview(data.system_devices, data.system_controls, cfg);
    if (reload.system) loadSystemForm(data);
    if (reload.device) loadDeviceForm(data);
  }
  renderCustomColorPalettes();
}

function loadSystemForm(data) {
  const sc = data.system_config || {};
  const cat = data.catalog || {};
  doc.getElementById("cfg-doorbell_noise_reduction").value = sc.doorbell_noise_reduction || "strong";
  const voListEl = doc.getElementById("volume-overrides-list");
  if (voListEl) {
    voListEl.innerHTML = "";
    (sc.volume_overrides || []).forEach(vo => addVolumeOverrideRow(vo.speaker, vo.target));
  }
  const remListEl = doc.getElementById("remotes-list");
  if (remListEl) {
    remListEl.innerHTML = "";
    (sc.remotes_list || []).forEach(rId => addRemoteControlRow(rId));
  }
  REMOTE_GROUPS_STATE = JSON.parse(JSON.stringify(sc.remote_groups || []));
  renderRemoteGroupsEditor();
  populateSelect("cfg-alarm_entity", cat.alarms, sc.alarm_entity);
  populateSelect("cfg-weather_entity", cat.weathers, sc.weather_entity);
  populateSelect("cfg-thermostat_entity", cat.climates, sc.thermostat_entity);
  populateSelect("cfg-lock_entity", cat.locks, sc.lock_entity);
  populateSelect("cfg-garage_entity", cat.garages, sc.garage_entity);
  populateSelect("cfg-vacuum_entity", cat.vacuums, sc.vacuum_entity);
  const camListEl = doc.getElementById("cameras-list");
  if (camListEl) {
    camListEl.innerHTML = "";
    (sc.camera_entities || []).forEach(cId => addCameraRow(cId));
  }
  const calListEl = doc.getElementById("calendars-list");
  if (calListEl) {
    calListEl.innerHTML = "";
    (sc.calendar_entities || []).forEach(cId => addCalendarRow(cId));
  }
}

function loadDeviceForm(data) {
  const cfg = data.config || {};
  const cat = data.catalog || {};
  doc.getElementById("cfg-device_slug").value = cfg.device_slug || "";
  doc.getElementById("cfg-default_page_size").value = cfg.default_page_size ?? 3;
  doc.getElementById("cfg-native_ble_tracking").checked = !!cfg.native_ble_tracking;
  doc.getElementById("cfg-ble_auto_switch").checked = !!cfg.ble_auto_switch;
  doc.getElementById("cfg-sync_device_area").checked = !!cfg.sync_device_area;
  doc.getElementById("row-sync-device-area")?.classList.toggle("hidden", data.capabilities?.is_roaming_device === false);
  doc.getElementById("row-area-follow-dwell")?.classList.toggle("hidden", data.capabilities?.is_roaming_device === false);
  const dwellEl = doc.getElementById("cfg-area_follow_dwell_s");
  if (dwellEl) dwellEl.value = String(cfg.area_follow_dwell_s ?? 10);
  renderDwellValue();
  doc.getElementById("cfg-area_handoff").checked = !!cfg.area_handoff;
  doc.getElementById("cfg-ble_beacon_uuid").value = cfg.ble_beacon_uuid || "";
  doc.getElementById("cfg-ble_target_address").value = cfg.ble_target_address || "";
  doc.getElementById("cfg-dock_apps").value = cfg.dock_apps || "";
  renderDockPillsFromInput();
  doc.getElementById("cfg-wallpaper_cycle_minutes").value = String(cfg.wallpaper_cycle_minutes || 0);
  populateSelect("cfg-default_area", cat.areas, cfg.default_area);
  populateSelect("cfg-presence_entity", cat.presence_sensors, cfg.presence_entity);
  populateSelect("cfg-assigned_person", cat.persons, cfg.assigned_person);
  populateSelect("cfg-default_speaker", cat.ma_speakers, cfg.default_speaker, true);
  populateSelect("cfg-ma_player_entity", cat.ma_players, cfg.ma_player_entity, true);
}

async function refreshState(forceForm=false) {
  const data = await callStudioWS({
    type: "latter/system/get_state",
    subentry_id: ACTIVE_SUBENTRY_ID || null,
    studio_rev: STUDIO_REV
  });
  if (data) {
    applyStateToDom(data, forceForm);
  } else if (!STATE) {
    // Nothing loaded yet: replace the loading state with an error and a Retry button.
    doc.getElementById("studio-root")?.classList.remove("is-loading");
    doc.getElementById("studio-load-error")?.classList.remove("hidden");
  }
}

function collectSystemSettings() {
  const volumeOverrides = [];
  doc.querySelectorAll("#volume-overrides-list .vol-override-row").forEach(row => {
    const speaker = row.querySelector(".vo-spk")?.value?.trim() || "";
    const target = row.querySelector(".vo-tgt")?.value?.trim() || "";
    if (speaker && target) volumeOverrides.push({speaker, target});
  });
  const rowValues = (selector) => {
    const out = [];
    doc.querySelectorAll(selector).forEach(sel => {
      const v = sel.value?.trim() || "";
      if (v && !out.includes(v)) out.push(v);
    });
    return out;
  };
  return {
    weather_entity: doc.getElementById("cfg-weather_entity")?.value ?? "",
    alarm_entity: doc.getElementById("cfg-alarm_entity")?.value ?? "",
    thermostat_entity: doc.getElementById("cfg-thermostat_entity")?.value ?? "",
    lock_entity: doc.getElementById("cfg-lock_entity")?.value ?? "",
    garage_entity: doc.getElementById("cfg-garage_entity")?.value ?? "",
    vacuum_entity: doc.getElementById("cfg-vacuum_entity")?.value ?? "",
    camera_entities: rowValues("#cameras-list .camera-row-item .cam-ent-sel"),
    remotes_list: rowValues("#remotes-list .remote-row-item .rem-ent-sel"),
    remote_groups: REMOTE_GROUPS_STATE,
    volume_overrides: volumeOverrides,
    calendar_entities: rowValues("#calendars-list .calendar-row-item .cal-ent-sel"),
    doorbell_noise_reduction: doc.getElementById("cfg-doorbell_noise_reduction")?.value || "strong"
  };
}

function collectDeviceSettings() {
  return {
    device_group: doc.getElementById("cfg-device_group")?.value || "unassigned",
    default_page_size: parseInt(doc.getElementById("cfg-default_page_size")?.value || "3", 10) || 3,
    native_ble_tracking: Boolean(doc.getElementById("cfg-native_ble_tracking")?.checked),
    ble_auto_switch: Boolean(doc.getElementById("cfg-ble_auto_switch")?.checked),
    sync_device_area: Boolean(doc.getElementById("cfg-sync_device_area")?.checked),
    area_handoff: Boolean(doc.getElementById("cfg-area_handoff")?.checked),
    ble_beacon_uuid: doc.getElementById("cfg-ble_beacon_uuid")?.value?.trim() || "",
    ble_target_address: doc.getElementById("cfg-ble_target_address")?.value?.trim() || "",
    presence_entity: doc.getElementById("cfg-presence_entity")?.value ?? "",
    assigned_person: doc.getElementById("cfg-assigned_person")?.value ?? "",
    default_speaker: doc.getElementById("cfg-default_speaker")?.value ?? "",
    ma_player_entity: doc.getElementById("cfg-ma_player_entity")?.value ?? "",
    default_area: doc.getElementById("cfg-default_area")?.value ?? "",
    dock_apps: doc.getElementById("cfg-dock_apps")?.value?.trim() || "",
    wallpaper_cycle_minutes: parseInt(doc.getElementById("cfg-wallpaper_cycle_minutes")?.value || "0", 10) || 0,
    area_follow_dwell_s: parseInt(doc.getElementById("cfg-area_follow_dwell_s")?.value || "10", 10) || 10
  };
}

function renderDwellValue() {
  const val = doc.getElementById("cfg-area_follow_dwell_s")?.value;
  const out = doc.getElementById("dwell-value");
  if (out) out.textContent = val ? `${fmtNumber(Number(val))} s` : "—";
}



let cwTargetScope = "device";
let cwSelectedHex = "";

function initColorWheel() {
  const canvas = doc.getElementById("latter-cw-canvas");
  if (!canvas || canvas.dataset.ready) return;
  canvas.dataset.ready = "1";
  const ctx = canvas.getContext("2d");
  const size = canvas.width;
  const cx = size / 2, cy = size / 2, r = size / 2 - 2;
  const img = ctx.createImageData(size, size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - cx, dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * size + x) * 4;
      if (dist <= r) {
        const hue = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
        const [cr, cg, cb] = hsvToRgbJS(hue, Math.min(1, dist / r), 1.0);
        img.data[idx] = cr; img.data[idx + 1] = cg; img.data[idx + 2] = cb; img.data[idx + 3] = 255;
      } else {
        img.data[idx + 3] = 0;
      }
    }
  }
  ctx.putImageData(img, 0, 0);
  let dragging = false;
  const pickAt = (ev) => {
    const rect = canvas.getBoundingClientRect();
    const x = (ev.touches ? ev.touches[0].clientX : ev.clientX) - rect.left;
    const y = (ev.touches ? ev.touches[0].clientY : ev.clientY) - rect.top;
    const dx = x - cx, dy = y - cy;
    const dist = Math.min(r, Math.sqrt(dx * dx + dy * dy));
    const hue = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
    const [cr, cg, cb] = hsvToRgbJS(hue, dist / r, 1.0);
    setCwHex("#" + [cr, cg, cb].map(v => v.toString(16).padStart(2, "0")).join("").toUpperCase());
  };
  canvas.addEventListener("mousedown", (e) => { dragging = true; pickAt(e); });
  window.addEventListener("mousemove", (e) => { if (dragging) pickAt(e); });
  window.addEventListener("mouseup", () => { dragging = false; });
  canvas.addEventListener("touchstart", (e) => { dragging = true; pickAt(e); e.preventDefault(); }, {passive: false});
  canvas.addEventListener("touchmove", (e) => { if (dragging) pickAt(e); e.preventDefault(); }, {passive: false});
  canvas.addEventListener("touchend", () => { dragging = false; });
}

function hsvToRgbJS(h, s, v) {
  let c = v * s;
  let x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  let m = v - c;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

function setCwHex(hex) {
  cwSelectedHex = String(hex || "").toUpperCase();
  const prev = doc.getElementById("latter-cw-preview");
  const inp = doc.getElementById("latter-cw-hex");
  if (prev) prev.style.setProperty("--swatch-color", cwSelectedHex);
  if (inp && getStudioActiveElement() !== inp) inp.value = cwSelectedHex;
}

function onCwHexInput(val) {
  let v = val.trim().toUpperCase();
  if (!v.startsWith("#")) v = "#" + v;
  if (/^#[0-9A-F]{6}$/.test(v)) {
    cwSelectedHex = v;
    doc.getElementById("latter-cw-preview")?.style.setProperty("--swatch-color", v);
  }
}

function openColorWheelModal(scope) {
  initColorWheel();
  cwTargetScope = scope || "device";
  const pals = STATE?.system_config?.custom_palettes || [];
  const start = STATE?.config?.device_custom_color || (pals[0] && pals[0].hex) || cssColorToHex(getComputedStyle(HOST_ELEMENT).getPropertyValue("--primary-color"));
  setCwHex(start);
  const nameInp = doc.getElementById("latter-cw-name");
  if (nameInp) nameInp.value = "";
  openDialog("latter-cw-modal");
}

function closeColorWheelModal() {
  closeDialog("latter-cw-modal");
}

async function saveSystemPalettes(pals) {
  const data = await callStudioCommand({command: "save_system_config", config: {custom_palettes: pals}});
  if (data) {
    applyStateToDom(data, false);
    showToast("Saved the color library");
  }
  return data;
}

async function saveColorWheelSelection() {
  const nameInp = doc.getElementById("latter-cw-name");
  const name = (nameInp && nameInp.value.trim()) ? nameInp.value.trim() : `Custom (${cwSelectedHex})`;
  const pals = (STATE?.system_config?.custom_palettes || []).map(p => ({...p}));
  const existing = pals.find(p => (p.hex || "").toUpperCase() === cwSelectedHex);
  if (existing) {
    existing.name = name;
  } else {
    pals.unshift({name, hex: cwSelectedHex});
  }
  closeColorWheelModal();
  const saved = await saveSystemPalettes(pals);
  if (saved && cwTargetScope === "device" && ACTIVE_SUBENTRY_ID) {
    await applyDeviceCustomColor(cwSelectedHex, true);
  }
}

async function applyDeviceCustomColor(hexColor, alsoSwitchSelect) {
  const data = await callStudioCommand({command: "save_device_config", config: {device_custom_color: hexColor.toUpperCase()}});
  if (!data) return;
  applyStateToDom(data, false);
  if (alsoSwitchSelect) {
    const secs = ((STATE.esphome || {}).sections || []);
    for (const s of secs) {
      for (const it of (s.items || [])) {
        if (it.domain === "select" && (it.name || "").toLowerCase().includes("color profile") && (it.options || []).includes("Custom")) {
          await espSelect(it.entity_id, "Custom");
        }
      }
    }
  }
  showToast("Applied the custom color");
}

async function onSelectDeviceCustomPalette(val) {
  if (val === "__new__") {
    openColorWheelModal("device");
    renderCustomColorPalettes();
    return;
  }
  if (val && val.startsWith("#")) {
    await applyDeviceCustomColor(val, true);
  }
}

async function deleteCustomPalette(hexColor) {
  const pals = (STATE?.system_config?.custom_palettes || []).filter(p => (p.hex || "").toUpperCase() !== hexColor.toUpperCase());
  await saveSystemPalettes(pals);
}

function renderCustomColorPalettes() {
  if (!STATE) return;
  const pals = STATE.system_config?.custom_palettes || [];
  const curHex = (STATE.config?.device_custom_color || "").toUpperCase();
  const sw = doc.getElementById("dev-color-swatch");
  if (sw && curHex) sw.style.setProperty("--swatch-color", curHex);
  const sel = doc.getElementById("dev-custom-palette-select");
  if (sel) {
    let optsHtml = "";
    if (curHex && !pals.some(p => (p.hex || "").toUpperCase() === curHex)) {
      optsHtml += `<option value="${esc(curHex)}" selected>Current (${esc(curHex)})</option>`;
    }
    for (const p of pals) {
      const h = (p.hex || "").toUpperCase();
      optsHtml += `<option value="${esc(h)}" ${h === curHex ? "selected" : ""}>${esc(p.name || h)} (${esc(h)})</option>`;
    }
    optsHtml += `<option value="__new__">Add a color…</option>`;
    sel.innerHTML = optsHtml;
  }
  const sysBox = doc.getElementById("sys-custom-palettes-list");
  if (sysBox) {
    sysBox.innerHTML = pals.length
      ? pals.map(p => {
          const h = (p.hex || "").toUpperCase();
          return settingsRowHtml(
            `<span class="swatch" style="--swatch-color:${esc(h)}" aria-hidden="true"></span> ${esc(p.name || h)}`,
            `<code>${esc(h)}</code>`,
            iconButtonHtml(ICON_DELETE, `Delete color ${p.name || h}`, `deleteCustomPalette(${jsArg(h)})`, "danger")
          );
        }).join("")
      : emptyStateHtml("No custom colors saved yet.");
  }
}



function bindStudioGlobals() {
  window.addCalendarRow = addCalendarRow;
  window.addCameraRow = addCameraRow;
  window.addRemoteControlRow = addRemoteControlRow;
  window.addRemoteGroupRow = addRemoteGroupRow;
  window.addVolumeOverrideRow = addVolumeOverrideRow;
  window.applyDeviceCustomColor = applyDeviceCustomColor;
  window.applyQuickProfileFromOverview = applyQuickProfileFromOverview;
  window.applySavedProfile = applySavedProfile;
  window.applyStateToDom = applyStateToDom;
  window.assignDeviceRemoteGroup = assignDeviceRemoteGroup;
  window.autoCalibrateHere = autoCalibrateHere;
  window.bulkNumber = bulkNumber;
  window.bulkSelect = bulkSelect;
  window.bulkToggle = bulkToggle;
  window.callStudioCommand = callStudioCommand;
  window.captureDeviceProfile = captureDeviceProfile;
  window.checkSystemUpdates = checkSystemUpdates;
  window.clearInternalLogs = clearInternalLogs;
  window.closeAddDeviceModal = closeAddDeviceModal;
  window.closeCameraPreviewBox = closeCameraPreviewBox;
  window.closeColorWheelModal = closeColorWheelModal;
  window.closeRemoveDeviceModal = closeRemoveDeviceModal;
  window.confirmAddDeviceModal = confirmAddDeviceModal;
  window.confirmRemoveManagedDevice = confirmRemoveManagedDevice;
  window.copyTextById = copyTextById;
  window.copyToClipboard = copyToClipboard;
  window.createDeviceGroup = createDeviceGroup;
  window.deleteCustomPalette = deleteCustomPalette;
  window.deleteDeviceGroup = deleteDeviceGroup;
  window.deleteSavedProfile = deleteSavedProfile;
  window.deleteWallpaper = deleteWallpaper;
  window.espAction = espAction;
  window.espNumber = espNumber;
  window.espSelect = espSelect;
  window.exportBackupToComputer = exportBackupToComputer;
  window.fallbackCopyText = fallbackCopyText;
    window.getInventoryRemoteIds = getInventoryRemoteIds;
  window.getRemoteFriendlyLabel = getRemoteFriendlyLabel;
  window.getSectionItems = getSectionItems;
  window.hsvToRgbJS = hsvToRgbJS;
  window.saveSetting = saveSetting;
  window.saveField = saveField;
  window.renderDwellValue = renderDwellValue;
  window.moveDockAppToken = moveDockAppToken;
  window.navigateToView = navigateToView;
  window.onAssignedPersonChanged = onAssignedPersonChanged;
  window.onCwHexInput = onCwHexInput;
  window.onFilterDeviceCategory = onFilterDeviceCategory;
  window.onSelectBleCandidate = onSelectBleCandidate;
  window.onSelectBleSurveyDevice = onSelectBleSurveyDevice;
  window.onSelectDeviceCustomPalette = onSelectDeviceCustomPalette;
  window.openAddDeviceModal = openAddDeviceModal;
  window.openColorWheelModal = openColorWheelModal;
  window.openDevicesLanding = openDevicesLanding;
  window.openDevicesWithCategory = openDevicesWithCategory;
  window.openNativeHaIntegrations = openNativeHaIntegrations;
  window.openNativeHaLogs = openNativeHaLogs;
  window.openHaPage = openHaPage;
  window.openDeviceInHa = openDeviceInHa;
  window.downloadDeviceDiagnostics = downloadDeviceDiagnostics;
  window.openSystemSection = openSystemSection;
  window.populateSelect = populateSelect;
  window.quickAdoptBleCandidate = quickAdoptBleCandidate;
  window.refreshActiveCameraPreview = refreshActiveCameraPreview;
  window.refreshState = refreshState;
  window.removeManagedDevice = removeManagedDevice;
  window.openResetDeviceModal = openResetDeviceModal;
  window.closeResetDeviceModal = closeResetDeviceModal;
  window.confirmResetDevice = confirmResetDevice;
  window.updateResetDeviceConfirm = updateResetDeviceConfirm;
  window.removeRemoteGroupRow = removeRemoteGroupRow;
  window.renderActiveSurveyDeviceBars = renderActiveSurveyDeviceBars;
  window.renderAreaPresenceGrid = renderAreaPresenceGrid;
  window.renderCameraPreview = renderCameraPreview;
  window.renderCohesiveDeviceSections = renderCohesiveDeviceSections;
  window.renderCustomColorPalettes = renderCustomColorPalettes;
  window.renderDeviceRemoteAssignments = renderDeviceRemoteAssignments;
  window.renderDiscoveredBleTable = renderDiscoveredBleTable;
  window.renderDockPillsFromInput = renderDockPillsFromInput;
  window.renderLogsView = renderLogsView;
  window.renderNativeControlRow = renderNativeControlRow;
  window.renderRawEntityList = renderRawEntityList;
  window.renderRemoteGroupsEditor = renderRemoteGroupsEditor;
  window.renderRssiBars = renderRssiBars;
  window.renderSystemOverview = renderSystemOverview;
  window.renderWallpaperGallery = renderWallpaperGallery;
  window.renumberCameraRows = renumberCameraRows;
  window.renumberRemoteControlRows = renumberRemoteControlRows;
  window.restoreFromUploadedFile = restoreFromUploadedFile;
  window.saveColorWheelSelection = saveColorWheelSelection;
  window.selectCurrentDevice = selectCurrentDevice;
  window.selectWallpaperSource = selectWallpaperSource;
  window.sendAnnouncement = sendAnnouncement;
  window.setAnnounceMode = setAnnounceMode;
  window.setAreaFusion = setAreaFusion;
  window.toggleFusionSensor = toggleFusionSensor;
  window.onFusionDetailsToggle = onFusionDetailsToggle;
  window.setBleOffset = setBleOffset;
  window.setCwHex = setCwHex;
  window.setScope = setScope;
  window.showToast = showToast;
    window.switchSystemDevice = switchSystemDevice;
  window.switchView = switchView;
  window.testDoorbellSpeaker = testDoorbellSpeaker;
  window.toggleDeviceTableSort = toggleDeviceTableSort;
  window.toggleDockAppToken = toggleDockAppToken;
  window.toggleParentHaSidebar = toggleParentHaSidebar;
  window.toggleRemoteInGroup = toggleRemoteInGroup;
  window.toggleSurveyFastMode = toggleSurveyFastMode;
  window.toggleWallpaperFav = toggleWallpaperFav;
  window.triggerHeaderFirmwareUpdate = triggerHeaderFirmwareUpdate;
  window.triggerJsonDownload = triggerJsonDownload;
  window.updateRemoteGroupField = updateRemoteGroupField;
  window.updateTopHeaderForScope = updateTopHeaderForScope;
  window.updateUnifiedPageTitle = updateUnifiedPageTitle;
  window.uploadWallpaperFile = uploadWallpaperFile;
  Object.defineProperty(window, "STATE", {
    get: () => STATE,
    configurable: true
  });
}

class LatterStudio extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._route = null;
    this._panel = null;
    this._initialized = false;
    this._subscribedSubentryId = null;
  }

  connectedCallback() {
    SHADOW_ROOT = this.shadowRoot;
    HOST_ELEMENT = this;
    bindStudioGlobals();
    if (!this._initialized) {
      this.shadowRoot.innerHTML = `<style>${STUDIO_STYLES}</style>${STUDIO_TEMPLATE}`;
      this._initialized = true;
      bindDialogs();
      this._applyRoute();
    }
    if (this._hass) {
      HASS_REF = this._hass;
      this._ensureSubscription();
    }
  }

  disconnectedCallback() {
    if (POLL_TIMER) {
      clearInterval(POLL_TIMER);
      POLL_TIMER = null;
    }
    this._teardownSubscription();
  }

  set hass(h) {
    const firstHass = !this._hass && !!h;
    this._hass = h;
    HASS_REF = h;
    if (this._initialized && firstHass) {
      this._ensureSubscription();
    }
  }

  get hass() {
    return this._hass;
  }

  set narrow(n) {
    this._narrow = Boolean(n);
    if (this._narrow) {
      this.setAttribute("narrow", "");
    } else {
      this.removeAttribute("narrow");
    }
  }

  get narrow() {
    return this._narrow;
  }

  set panel(p) {
    this._panel = p;
  }

  get panel() {
    return this._panel;
  }

  set route(r) {
    const prevPath = this._route ? this._route.path : null;
    this._route = r;
    if (this._initialized && r && r.path !== prevPath) {
      this._applyRoute();
    }
  }

  get route() {
    return this._route;
  }

  _applyRoute() {
    const parts = String((this._route && this._route.path) || "").split("/").filter(Boolean).map(decodeURIComponent);
    ROUTE_APPLYING = true;
    try {
      if (parts[0] === "devices" && parts[1]) {
        const viewId = slugToView(DEVICE_VIEW_SLUGS, parts[2] || "overview") || "dashboard";
        const changed = ACTIVE_SUBENTRY_ID !== parts[1];
        if (!changed && DEVICE_SELECTED && CURRENT_SCOPE === "device" && CURRENT_VIEW_ID === viewId) return;
        ACTIVE_SUBENTRY_ID = parts[1];
        DEVICE_SELECTED = true;
        setScope("device", viewId);
        if (changed && this._hass) {
          this._resubscribe(true);
        }
      } else if (parts[0] === "system") {
        const viewId = slugToView(SYSTEM_VIEW_SLUGS, parts[1] || "overview") || "system_overview";
        if (CURRENT_SCOPE === "system" && CURRENT_VIEW_ID === viewId) return;
        setScope("system", viewId);
      } else {
        DEVICE_SELECTED = false;
        setScope("device", "select_device_prompt");
      }
    } finally {
      ROUTE_APPLYING = false;
    }
  }

  _teardownSubscription() {
    SUB_GEN += 1;
    if (typeof WS_UNSUB === "function") {
      try {
        WS_UNSUB();
      } catch (_e) {}
    }
    WS_UNSUB = null;
    this._subscribedSubentryId = null;
  }

  _resubscribe(doRefresh=false) {
    this._teardownSubscription();
    return this._ensureSubscription(doRefresh);
  }

  async _ensureSubscription(doRefresh=true) {
    if (!this._hass || !this._hass.connection) return;
    const myGen = ++SUB_GEN;
    const targetSubId = ACTIVE_SUBENTRY_ID || null;
    if (doRefresh || !STATE) {
      await refreshState(true);
    }
    if (myGen !== SUB_GEN) return;
    try {
      const unsub = await this._hass.connection.subscribeMessage(
        (eventPayload) => {
          if (myGen !== SUB_GEN || !eventPayload) return;
          if (
            ACTIVE_SUBENTRY_ID &&
            eventPayload.subentry_id &&
            eventPayload.subentry_id !== ACTIVE_SUBENTRY_ID
          ) {
            return;
          }
          applyStateToDom(eventPayload, {system: canReloadForm("system"), device: canReloadForm("device")});
        },
        {
          type: "latter/system/subscribe",
          subentry_id: targetSubId,
          studio_rev: STUDIO_REV
        }
      );
      if (myGen !== SUB_GEN) {
        if (typeof unsub === "function") {
          try {
            unsub();
          } catch (_e) {}
        }
        return;
      }
      WS_UNSUB = unsub;
      this._subscribedSubentryId = targetSubId || "";
    } catch (err) {
      console.warn("Latter Studio WS subscription fallback to polling:", err);
      if (POLL_TIMER) clearInterval(POLL_TIMER);
      POLL_TIMER = setInterval(() => refreshState({system: canReloadForm("system"), device: canReloadForm("device")}), 5000);
    }
  }
}

if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
