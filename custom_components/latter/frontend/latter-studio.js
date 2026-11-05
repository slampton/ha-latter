/**
 * Latter Studio — Native Home Assistant Custom Panel (`panel_custom` Web Component)
 * Zero external dependencies; communicates exclusively via admin-gated `websocket_api`.
 */

const STUDIO_STYLES = `
  :host {
    display: block;
    min-height: 100vh;
    --bg: var(--primary-background-color, #111111);
    --sidebar: var(--secondary-background-color, #1c1c1c);
    --card: var(--card-background-color, var(--ha-card-background, #1c1c1c));
    --card-hover: rgba(3, 169, 244, 0.08);
    --border: var(--divider-color, rgba(225, 225, 225, 0.12));
    --input-bg: var(--input-fill-color, var(--secondary-background-color, #141414));
    --text: var(--primary-text-color, #e1e1e1);
    --text-strong: var(--primary-text-color, #e1e1e1);
    --muted: var(--secondary-text-color, #9b9b9b);
    --accent: var(--primary-color, #03a9f4);
    --accent-solid: var(--primary-color, #03a9f4);
    --accent-subtle: rgba(3, 169, 244, 0.14);
    --success: var(--success-color, #4caf50);
    --warning: var(--warning-color, #ff9800);
    --danger: var(--error-color, #db4437);
    background: var(--bg);
    color: var(--text);
    font-family: var(--paper-font-body1_-_font-family, Roboto, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
    font-size: 14px;
    line-height: 1.45;
    -webkit-tap-highlight-color: transparent;
  }
  :host([narrow]) .ha-menu-btn {
    display: inline-flex;
  }
  * { box-sizing: border-box; }
  .studio-root {
    margin: 0;
    font-family: Roboto, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    font-size: 14px;
    line-height: 1.45;
    -webkit-tap-highlight-color: transparent;
  }
  code, .mono {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
  }
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    padding: 0 20px 0 16px;
    background: var(--sidebar);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 30;
    gap: 12px;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 20px;
    font-weight: 500;
    color: var(--text-strong);
    user-select: none;
  }
  .titlebar-brand svg.brand-logo {
    width: 22px;
    height: 22px;
    fill: var(--accent);
    flex-shrink: 0;
  }
  .ha-menu-btn {
    display: none;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    margin-right: 2px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-strong);
    cursor: pointer;
  }
  .ha-menu-btn:hover {
    background: var(--card-hover);
  }
  .ha-menu-btn svg {
    width: 22px;
    height: 22px;
    fill: currentColor;
  }
  .app-shell {
    display: grid;
    grid-template-columns: 244px minmax(0, 1fr);
    min-height: calc(100vh - 56px);
  }

  /* NATIVE HOME ASSISTANT SIDEBAR */
  aside.sidebar {
    background: var(--sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 16px 12px 12px;
    position: sticky;
    top: 56px;
    height: calc(100vh - 56px);
    overflow-y: auto;
  }
  .scope-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 10px;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    background: var(--input-bg);
    padding: 3px;
    border-radius: 7px;
    border: 1px solid var(--border);
  }
  .scope-tab {
    padding: 6px 8px;
    border-radius: 5px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    text-align: center;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .scope-tab.active {
    background: var(--accent-solid);
    color: #ffffff;
    font-weight: 600;
  }
  .device-picker-wrap {
    margin-top: 8px;
  }
  .device-picker-wrap label {
    display: block;
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .device-picker-wrap select {
    padding: 7px 9px;
    font-size: 13px;
    font-weight: 500;
  }
  .nav-device-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-strong);
    margin: 6px 0 6px;
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) {
    margin-left: 10px;
    width: calc(100% - 10px);
    padding: 8px 12px;
  }
  .nav-group-label:first-child {
    margin-top: 4px;
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    margin: 0;
    padding: 9px 12px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text);
    font-weight: 500;
    font-size: 13.5px;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .nav-btn:hover {
    background: var(--card-hover);
  }
  .nav-btn.active {
    background: var(--accent-subtle);
    color: var(--accent);
    font-weight: 600;
  }
  .nav-badge {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 10px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .sidebar-footer {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }

  /* MAIN AREA & TOPBAR */
  .main-area {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  header.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 24px;
    background: var(--sidebar);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 15;
    flex-wrap: wrap;
    gap: 10px;
  }
  .topbar-status {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 16px;
    background: var(--card);
    border: 1px solid var(--border);
    font-size: 12px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }
  .dot-live {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
  }
  .topbar-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dirty-banner {
    display: none;
    align-items: center;
    font-size: 12px;
    font-weight: 600;
    color: var(--warning);
    background: rgba(255, 152, 0, 0.12);
    border: 1px solid rgba(255, 152, 0, 0.35);
    padding: 4px 10px;
    border-radius: 16px;
  }
  .dirty-banner.visible { display: inline-flex; }

  /* BUTTONS */
  button.btn-primary {
    background: var(--accent-solid);
    color: #ffffff;
    border: 1px solid transparent;
    padding: 8px 14px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
    transition: opacity 0.15s ease, background 0.15s ease;
  }
  button.btn-primary:disabled {
    background: var(--card);
    color: var(--muted);
    border: 1px solid var(--border);
    opacity: 0.65;
    cursor: default;
  }
  button.btn-secondary {
    background: var(--card);
    color: var(--text-strong);
    border: 1px solid var(--border);
    padding: 8px 13px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
  }
  button.btn-secondary:hover {
    background: var(--card-hover);
    border-color: var(--accent);
  }
  button.btn-chip {
    background: rgba(3, 169, 244, 0.16);
    color: var(--text-strong);
    border: 1px solid var(--accent);
    padding: 8px 14px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
  }
  button.btn-chip:hover {
    background: var(--accent-solid);
    border-color: var(--accent-solid);
    color: #ffffff;
  }
  button.btn-danger {
    background: rgba(219, 68, 55, 0.12);
    color: var(--danger);
    border: 1px solid rgba(219, 68, 55, 0.3);
    padding: 7px 11px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    font-size: 12.5px;
    white-space: nowrap;
  }

  /* CONTENT & CARDS */
  .content-wrap {
    max-width: 1140px;
    width: 100%;
    margin: 0 auto;
    padding: 20px 24px 64px;
  }
  .unified-page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }
  .unified-page-header h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-strong);
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }
  .unified-page-header h2 .header-device-sub {
    font-size: 17.5px;
    font-weight: 400;
    color: var(--muted);
    letter-spacing: normal;
  }
  .content-wrap > section > .page-header {
    display: none !important;
  }
  .page-header > p,
  .card > p.desc,
  .card > div > p.desc,
  .card > div > div > p.desc,
  .details-body > p.desc {
    display: none !important;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  .form-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  .form-grid-3 {
    display: grid;
    grid-template-columns: 1.2fr 1.2fr 0.8fr;
    gap: 10px;
  }
  .input-action-row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .input-action-row > input,
  .input-action-row > select {
    flex: 1 1 180px;
    min-width: 0;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    min-width: 0;
    margin-bottom: 16px;
  }
  .grid-2 > .card {
    margin-bottom: 0;
  }
  .card h3 {
    margin: 0 0 18px;
    font-size: 17.5px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-strong);
  }
  .card p.desc {
    margin: 0 0 14px;
    font-size: 13px;
    color: var(--muted);
  }
  .hero-stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .theme-icon-group {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    background: var(--input-bg);
    padding: 4px;
    border-radius: 9px;
    border: 1px solid var(--border);
  }
  .theme-icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 32px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .theme-icon-btn:hover {
    color: var(--text-strong);
    background: var(--card-hover);
  }
  .theme-icon-btn.active {
    background: var(--text-strong);
    color: var(--bg);
  }
  .theme-icon-btn svg {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .update-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 11px;
    border-radius: 16px;
    background: rgba(3, 169, 244, 0.18);
    border: 1px solid var(--accent);
    color: var(--text-strong);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .update-pill:hover {
    background: var(--accent-solid);
    color: #ffffff;
  }
  .stat-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 11px 14px;
  }
  .stat-box span {
    display: block;
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    margin-bottom: 2px;
  }
  .stat-box strong {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-strong);
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
  }
  .field { margin-bottom: 13px; }
  .field:last-child { margin-bottom: 0; }
  .field label {
    display: block;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--muted);
    margin-bottom: 5px;
  }
  select, input[type="text"], input[type="password"], input[type="number"] {
    width: 100%;
    padding: 8px 11px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--input-bg);
    color: var(--text-strong);
    font-size: 13.5px;
  }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13.5px;
    gap: 12px;
  }
  .toggle-row:last-child { border-bottom: none; }
  .summary-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13.5px;
    gap: 10px;
  }
  .summary-row:last-child { border-bottom: none; }
  .summary-row span { color: var(--muted); }
  .summary-row strong { color: var(--text-strong); font-weight: 500; }
  .summary-row.clickable {
    cursor: pointer;
    margin: 0 -8px;
    padding: 9px 8px;
    border-radius: 7px;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .summary-row.clickable:hover {
    background: var(--card-hover);
  }
  .summary-row.clickable:hover span {
    color: var(--text-strong);
  }
  .summary-row.clickable strong::after {
    content: " ›";
    color: var(--muted);
    font-weight: 400;
    margin-left: 6px;
  }

  /* EXPANDABLE HA DETAILS PANELS */
  details.ha-details {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 12px;
    overflow: hidden;
  }
  details.ha-details > summary {
    padding: 14px 18px;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text-strong);
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    user-select: none;
  }
  details.ha-details > summary::-webkit-details-marker { display: none; }
  details.ha-details > summary::after {
    content: "▾";
    color: var(--muted);
    font-size: 14px;
    transition: transform 0.15s ease;
  }
  details.ha-details[open] > summary {
    border-bottom: 1px solid var(--border);
  }
  details.ha-details[open] > summary::after {
    transform: rotate(180deg);
  }
  .details-body {
    padding: 16px 18px;
  }

  /* HOME ASSISTANT SORTABLE DATA TABLE */
  .ha-table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--input-bg);
  }
  table.ha-data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 13.5px;
  }
  table.ha-data-table thead th {
    padding: 10px 14px;
    font-size: 11.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    transition: color 0.12s ease, background 0.12s ease;
  }
  table.ha-data-table thead th:hover {
    color: var(--text-strong);
    background: var(--card-hover);
  }
  table.ha-data-table thead th.sorted {
    color: var(--accent);
  }
  table.ha-data-table tbody tr {
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.12s ease;
  }
  table.ha-data-table tbody tr:last-child {
    border-bottom: none;
  }
  table.ha-data-table tbody tr:hover {
    background: var(--card-hover);
  }
  table.ha-data-table tbody td {
    padding: 11px 14px;
    color: var(--text);
    white-space: nowrap;
  }
  table.ha-data-table tbody td.col-name {
    font-weight: 500;
    color: var(--text-strong);
  }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .status-dot.online { background: var(--success); }
  .status-dot.offline { background: var(--muted); opacity: 0.5; }
  .status-dot.update { background: var(--warning); }

  /* ENTITY ROWS & LISTS */
  .native-controls-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .native-ctrl-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 12px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .native-ctrl-row .lbl {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--text-strong);
    min-width: 0;
  }
  .native-ctrl-row .lbl small {
    display: block;
    font-weight: 400;
    font-size: 11.5px;
    color: var(--muted);
    margin-top: 1px;
  }
  .native-ctrl-row .widget {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .native-ctrl-row select {
    width: auto;
    min-width: 145px;
    max-width: 220px;
    padding: 6px 10px;
  }
  .native-ctrl-row input[type="range"] {
    width: 120px;
    accent-color: var(--accent-solid);
  }
  .state-badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 12px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--accent);
    font-weight: 500;
    font-size: 11.5px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* QUICK ACTIONS & AREA MINI CARDS */
  .quick-actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .area-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
    gap: 8px;
  }
  .area-mini-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 9px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    cursor: pointer;
    transition: border-color 0.12s ease, background 0.12s ease;
  }
  .area-mini-card.on {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .area-mini-card strong {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-strong);
    display: block;
  }
  .area-mini-card small {
    font-size: 11px;
    color: var(--muted);
  }

  /* DOCK PILL SELECTOR */
  .dock-pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .dock-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 16px;
    font-size: 12.5px;
    font-weight: 500;
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--muted);
    cursor: pointer;
    user-select: none;
  }
  .dock-pill.enabled {
    background: var(--accent-subtle);
    border-color: var(--accent);
    color: var(--text-strong);
  }
  .dock-pill .move-arrow {
    font-size: 11px;
    padding: 0 3px;
    color: var(--muted);
  }
  .dock-pill .move-arrow:hover {
    color: var(--accent);
  }

  /* RSSI & GALLERIES */
  .rssi-track {
    height: 7px;
    background: var(--input-bg);
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  .rssi-fill {
    height: 100%;
    background: var(--accent-solid);
    border-radius: 4px;
    transition: width 0.25s ease;
  }
  .remote-slot-card {
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .remote-slot-card.active-slot {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .remote-slot-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .remote-slot-hdr strong {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--text-strong);
  }
  .wp-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    margin-top: 12px;
  }
  .wp-card {
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    text-align: center;
  }
  .wp-card.active {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .wp-thumb {
    width: 104px;
    height: 104px;
    object-fit: cover;
    border: 1px solid var(--border);
    background: #000;
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: 8px; }
  .wp-title {
    font-size: 12.5px;
    font-weight: 500;
    color: var(--text-strong);
  }
  .wp-actions {
    display: flex;
    gap: 5px;
    width: 100%;
    justify-content: center;
    margin-top: auto;
  }
  .chip-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip {
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--text-strong);
    padding: 4px 10px;
    border-radius: 14px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .chip b { cursor: pointer; color: var(--danger); }
  .toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: var(--card);
    color: var(--text-strong);
    border: 1px solid var(--accent);
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 13px;
    display: none;
    z-index: 50;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
  }
  .hidden { display: none !important; }

  /* PHONE & TABLET RESPONSIVE BREAKPOINTS */
  @media (max-width: 860px) {
    .ha-menu-btn { display: inline-flex; }
    .app-shell { grid-template-columns: 1fr; }
    aside.sidebar {
      position: sticky;
      top: 56px;
      z-index: 25;
      height: auto;
      padding: 8px 12px;
      border-right: none;
      border-bottom: 1px solid var(--border);
    }
    .scope-box {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px;
      margin-bottom: 6px;
    }
    .scope-tabs { flex: 0 0 150px; }
    .device-picker-wrap {
      margin-top: 0;
      flex: 1;
      min-width: 0;
    }
    .device-picker-wrap label { display: none; }
    .nav-device-title { display: none; }
    .nav-list {
      flex-direction: row;
      overflow-x: auto;
      padding-bottom: 2px;
      gap: 6px;
      scrollbar-width: none;
    }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn {
      width: auto;
      border-radius: 16px;
      padding: 6px 12px;
      font-size: 12.5px;
      background: var(--card);
      border: 1px solid var(--border);
    }
    .sidebar-footer { display: none; }
    header.topbar {
      position: static;
      padding: 8px 14px;
    }
    #topbar-device-chips, #topbar-system-chips {
      display: none !important;
    }
    .content-wrap { padding: 14px 12px 72px; }
    .grid-2 { grid-template-columns: 1fr; }
    .hero-stats { grid-template-columns: 1fr; }
    .native-ctrl-row {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;
    }
    .native-ctrl-row .widget { justify-content: space-between; }
    .native-ctrl-row select { max-width: 100%; width: 100%; }
  }
  @media (max-width: 640px) {
    .form-grid-2, .form-grid-3 {
      grid-template-columns: 1fr;
    }
    .scope-box {
      flex-direction: column;
      align-items: stretch;
    }
    .scope-tabs { flex: none; }
  }
`;

const STUDIO_TEMPLATE = `<div class="studio-root">
<header class="latter-top-titlebar">
  <div class="titlebar-brand">
    <button type="button" class="ha-menu-btn" title="Toggle Home Assistant Sidebar" onclick="toggleParentHaSidebar()">
      <svg viewBox="0 0 24 24"><path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z"/></svg>
    </button>
    <svg class="brand-logo" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h1A1.5 1.5 0 0 1 8 5.5v13A1.5 1.5 0 0 1 6.5 20h-1A1.5 1.5 0 0 1 4 18.5v-13ZM16 5.5A1.5 1.5 0 0 1 17.5 4h1A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-1A1.5 1.5 0 0 1 16 18.5v-13ZM4 16.5h16v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2ZM8 5.25h8v2.5H8v-2.5ZM8 10.75h8v2.5H8v-2.5Z"/></svg>
    <span>Latter</span>
  </div>
  <div class="topbar-actions">
    <button type="button" id="hdr-update-pill" class="update-pill hidden" onclick="triggerHeaderFirmwareUpdate()">Update Available</button>
    <div id="dirty-indicator" class="dirty-banner">Unsaved</div>
    <button id="btn-save-changes" class="btn-primary" disabled onclick="saveAllConfig()">Saved</button>
  </div>
</header>
<div class="app-shell">
  <!-- LEFT SIDEBAR: SYSTEM (6 TABS) vs DEVICE (5 TABS) -->
  <aside class="sidebar">
    <div class="scope-box">
      <div class="scope-tabs">
        <button class="scope-tab" id="tab-scope-system" onclick="setScope('system')">System</button>
        <button class="scope-tab active" id="tab-scope-device" onclick="openDevicesLanding()">Devices</button>
      </div>
    </div>

    <!-- SYSTEM NAVIGATION (6 TABS) -->
    <div class="nav-list hidden" id="nav-scope-system">
      <button class="nav-btn" data-view="system_overview" onclick="switchView('system_overview', this)">
        <span>Overview</span>
      </button>
      <button class="nav-btn" data-view="shared_entities" onclick="switchView('shared_entities', this)">
        <span>Shared Entities</span>
      </button>
      <button class="nav-btn" data-view="remotes" onclick="switchView('remotes', this)">
        <span>Media &amp; Remotes</span>
      </button>
      <button class="nav-btn" data-view="system_sync" onclick="switchView('system_sync', this)">
        <span>Groups &amp; Profiles</span>
      </button>
      <button class="nav-btn" data-view="area_tracking" onclick="switchView('area_tracking', this)">
        <span>BLE &amp; Area Presence</span>
      </button>
      <button class="nav-btn" data-view="system_admin" onclick="switchView('system_admin', this)">
        <span>Administration</span>
      </button>
    </div>

    <!-- DEVICES LIST SIDEBAR (WHEN ON ALL DEVICES LANDING PAGE) -->
    <div class="nav-list hidden" id="nav-scope-devices-list">
      <button class="nav-btn active" data-view="select_device_prompt" onclick="openDevicesLanding()">
        <span>All Devices</span>
        <span class="nav-badge" id="nav-system-count">1</span>
      </button>
    </div>

    <!-- SELECTED DEVICE NAVIGATION (5 TABS) -->
    <div class="nav-list" id="nav-scope-device">
      <button class="nav-btn nav-back-btn" style="color:var(--muted);" onclick="openDevicesLanding()">
        <span>&larr; All Devices</span>
      </button>
      <div class="nav-device-title" id="nav-selected-device-label">Device</div>
      <button class="nav-btn active" data-view="dashboard" onclick="switchView('dashboard', this)">
        <span>Overview</span>
      </button>
      <button class="nav-btn" id="nav-btn-home_display" data-view="home_display" onclick="switchView('home_display', this)">
        <span>Display &amp; Home</span>
      </button>
      <button class="nav-btn" id="nav-btn-audio_voice" data-view="audio_voice" onclick="switchView('audio_voice', this)">
        <span>Audio &amp; Voice</span>
      </button>
      <button class="nav-btn" id="nav-btn-power" data-view="power" onclick="switchView('power', this)">
        <span>Power &amp; Battery</span>
      </button>
      <button class="nav-btn" data-view="system" onclick="switchView('system', this)">
        <span>Administration</span>
        <span class="nav-badge" id="nav-esp-badge">0</span>
      </button>
    </div>

  </aside>

  <!-- MAIN AREA -->
  <div class="main-area">
    <div class="content-wrap">
      <div class="unified-page-header">
        <h2 id="unified-page-title">Overview</h2>
      </div>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 1: SYSTEM OVERVIEW                                      -->
      <!-- ================================================================== -->
      <section id="view-system_overview" class="hidden">
        <div class="page-header">
          <h2>Overview</h2>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>System</h3>
            <div class="summary-row">
              <span>Latter Version</span>
              <div style="display:flex;align-items:center;gap:8px;">
                <strong id="sys-sum-version">v2.2.0</strong>
                <button type="button" class="btn-secondary" style="padding:3px 9px;font-size:11.5px;" onclick="checkSystemUpdates()">Check for Updates</button>
              </div>
            </div>
            <div class="summary-row clickable" onclick="openDevicesWithCategory('all')">
              <span>Online / Active Devices</span><strong id="sys-sum-online">0 / 0</strong>
            </div>
            <div class="summary-row clickable" onclick="openDevicesWithCategory('native')">
              <span>Latter Native Devices</span><strong id="sys-sum-native">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openDevicesWithCategory('ble_tracked')">
              <span>BLE Tracked Devices</span><strong id="sys-sum-ble-tracked">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openDevicesWithCategory('ble_tracked')">
              <span>People Tracked (BLE Area)</span><strong id="sys-sum-people">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openSystemSection('area_tracking', '')">
              <span>BLE Area Proxies</span><strong id="sys-sum-proxies">0</strong>
            </div>
          </div>

          <div class="card">
            <h3>Configured Integrations</h3>
            <div class="summary-row clickable" onclick="openSystemSection('remotes', 'card-remotes')">
              <span>Remote Controls</span><strong id="sys-sum-remotes">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openSystemSection('remotes', 'card-vol-overrides')">
              <span>Speaker Volume Overrides</span><strong id="sys-sum-vol">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openSystemSection('shared_entities', 'card-cameras')">
              <span>Cameras</span><strong id="sys-sum-cameras">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openSystemSection('shared_entities', 'card-calendars')">
              <span>Calendars</span><strong id="sys-sum-calendars">0</strong>
            </div>
            <div class="summary-row clickable" onclick="openSystemSection('system_sync', '')">
              <span>Groups &amp; Saved Profiles</span><strong id="sys-sum-groups-profiles">0</strong>
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 2: SHARED ENTITIES (WHOLE-HOME, CAMERAS, CALENDARS)     -->
      <!-- ================================================================== -->
      <section id="view-shared_entities" class="hidden">
        <div class="page-header">
          <h2>Shared Entities</h2>
          <p>Select shared system entities, cameras, and calendars.</p>
        </div>

        <div class="grid-2">
          <!-- CARD 1: WHOLE-HOME ENTITIES -->
          <div class="card">
            <h3>Whole-Home Entities</h3>
            <p class="desc">Primary shared system entities used by the Home screen and Whole-Home Hub.</p>
            <div class="field">
              <label>Weather Provider (weather.*)</label>
              <select id="cfg-weather_entity" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Security Alarm (alarm_control_panel.*)</label>
              <select id="cfg-alarm_entity" onchange="markDirty()"></select>
            </div>
            <div class="form-grid-2">
              <div class="field">
                <label>Thermostat (climate.*)</label>
                <select id="cfg-thermostat_entity" onchange="markDirty()"></select>
              </div>
              <div class="field">
                <label>Entry Lock (lock.*)</label>
                <select id="cfg-lock_entity" onchange="markDirty()"></select>
              </div>
            </div>
            <div class="form-grid-2">
              <div class="field">
                <label>Garage Door (cover.*)</label>
                <select id="cfg-garage_entity" onchange="markDirty()"></select>
              </div>
              <div class="field">
                <label>Robot Vacuum (vacuum.*)</label>
                <select id="cfg-vacuum_entity" onchange="markDirty()"></select>
              </div>
            </div>
          </div>

          <!-- CARD 2: CAMERAS & DOORBELL AUDIO -->
          <div class="card" id="card-cameras">
            <h3>Cameras &amp; Doorbell Audio</h3>
            <p class="desc">Add up to 10 <code>camera.*</code> entities for the on-device Camera Carousel and doorbell popups. Devices can listen to a doorbell and reply by push-to-talk: your speech is transcribed and spoken on the camera's speaker with Home Assistant TTS.</p>
            <div class="field">
              <label>Doorbell audio noise reduction</label>
              <div class="input-action-row">
                <select id="cfg-doorbell_noise_reduction" onchange="markDirty()">
                  <option value="strong">Strong</option>
                  <option value="light">Light</option>
                  <option value="off">Off</option>
                </select>
                <button type="button" class="btn-secondary" onclick="testDoorbellSpeaker()">Test door speaker</button>
              </div>
            </div>
            <div id="cameras-list"></div>
            <button type="button" class="btn-secondary" id="btn-add-camera" onclick="addCameraRow(''); markDirty();">+ Add Camera</button>

            <div id="cam-preview-box" style="display:none;flex-direction:column;gap:8px;margin-top:14px;padding:12px;background:var(--input-bg);border:1px solid var(--border);border-radius:10px;">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <strong id="cam-preview-label" style="font-size:13px;font-weight:500;color:var(--text-strong);">Camera Snapshot Preview</strong>
                <div style="display:flex;gap:6px;">
                  <button type="button" class="btn-secondary" style="padding:4px 10px;font-size:12px;" onclick="refreshActiveCameraPreview()">Refresh</button>
                  <button type="button" class="btn-secondary" style="padding:4px 8px;font-size:12px;" onclick="closeCameraPreviewBox()">Close</button>
                </div>
              </div>
              <img id="cam-preview-img" style="width:100%;max-width:360px;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:8px;border:1px solid var(--border);background:#000;" alt="Camera Snapshot">
            </div>
          </div>
        </div>

        <div class="grid-2">
          <!-- CARD 3: CALENDARS -->
          <div class="card" id="card-calendars">
            <h3>Calendars</h3>
            <p class="desc">Add shared calendars (<code>calendar.*</code>) to aggregate upcoming events in the Agenda tool and Home screen.</p>
            <div id="calendars-list"></div>
            <button type="button" class="btn-secondary" onclick="addCalendarRow(''); markDirty();">+ Add Calendar</button>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 3: MEDIA & REMOTES (REMOTES + SPEAKER VOLUME OVERRIDES) -->
      <!-- ================================================================== -->
      <section id="view-remotes" class="hidden">
        <div class="page-header">
          <h2>Media &amp; Remotes</h2>
          <p>Assign up to 10 TV/media remotes and configure speaker volume overrides.</p>
        </div>

        <div class="card" id="card-remotes">
          <h3>System Remote Inventory</h3>
          <p class="desc">Add up to 10 <code>remote.*</code> or <code>media_player.*</code> entities across your site. Once added here, organize them into Area or Device Remote Groups below.</p>
          <div id="remotes-list"></div>
          <button type="button" class="btn-secondary" id="btn-add-remote" onclick="addRemoteControlRow(''); markDirty();">+ Add Remote Control</button>
        </div>

        <div class="card" id="card-remote-groups">
          <h3>Remote Control Groups (Area &amp; Device Assignment)</h3>
          <p class="desc">Create groups of remotes and assign them to an <strong>Area</strong> (so roaming devices automatically see that Area's remotes when present, or hide the Remote app when an Area has none) or assign a group statically to a specific device.</p>
          <div id="remote-groups-list"></div>
          <button type="button" class="btn-secondary" onclick="addRemoteGroupRow(); markDirty();">+ Create Remote Group</button>

          <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--border);">
            <h4 style="margin:0 0 10px;font-size:14.5px;font-weight:600;color:var(--text-strong);">Device Remote Assignment</h4>
            <div id="device-remote-assignments-list" class="native-controls-box"></div>
          </div>
        </div>

        <div class="card" id="card-vol-overrides">
          <h3>Speaker Volume Overrides</h3>
          <p class="desc">When streaming audio to a specific speaker, route volume commands to a different media player or number entity instead.</p>
          <div id="volume-overrides-list"></div>
          <button type="button" class="btn-secondary" id="btn-add-vol-override" onclick="addVolumeOverrideRow('', ''); markDirty();">+ Add Volume Override</button>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 4: GROUPS & PROFILES                                    -->
      <!-- ================================================================== -->
      <section id="view-system_sync" class="hidden">
        <div class="page-header">
          <h2>Groups &amp; Profiles</h2>
          <p>Organize devices into groups, save configuration profiles, and apply settings across multiple devices.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Configuration Profiles</h3>
            <p class="desc">Capture settings from <strong id="prof-active-dev-label">Active Device</strong> as a reusable profile, or apply a profile to any device or group.</p>
            <div class="input-action-row" style="margin-bottom:12px;">
              <input type="text" id="new-profile-name" placeholder="Profile Name (e.g. Nightstand)">
              <input type="text" id="new-profile-desc" placeholder="Description (optional)">
              <button class="btn-primary" onclick="captureCurrentDeviceProfile()">Capture Profile</button>
            </div>
            <div class="field">
              <label>Apply Profile Target</label>
              <select id="profile-target-scope"></select>
            </div>
            <div id="saved-profiles-list" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Device Groups</h3>
            <p class="desc">Assign devices to logical groups for targeted profile deployment and bulk control.</p>
            <div class="input-action-row" style="margin-bottom:12px;">
              <input type="text" id="new-group-name" placeholder="New Group Name">
              <input type="text" id="new-group-desc" placeholder="Description">
              <button class="btn-secondary" onclick="createDeviceGroup()">+ Add Group</button>
            </div>
            <div id="device-groups-list" class="native-controls-box"></div>
          </div>
        </div>

        <details class="ha-details">
          <summary>Bulk Device Controls (Multi-Device Live Settings)</summary>
          <div class="details-body">
            <p class="desc" style="margin:0 0 12px;color:var(--muted);font-size:13px;">Dispatch display, sleep, voice, or sound changes simultaneously across all devices or a selected group.</p>
            <div class="form-grid-2" style="margin-bottom:12px;">
              <div>
                <label style="display:block;font-size:12px;color:var(--muted);margin-bottom:4px;">Category</label>
                <select id="group-ctrl-cat-filter" onchange="renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config)">
                  <option value="display">Display &amp; Appearance</option>
                  <option value="sleep">Sleep &amp; Wake</option>
                  <option value="voice">Voice Assistant</option>
                  <option value="sound">Sound &amp; Alerts</option>
                  <option value="music">Music &amp; Media</option>
                  <option value="all">All Categories</option>
                </select>
              </div>
              <div>
                <label style="display:block;font-size:12px;color:var(--muted);margin-bottom:4px;">Target Devices</label>
                <select id="group-ctrl-filter" onchange="renderSystemOverview(STATE.system_devices, STATE.system_controls, STATE.config)"></select>
              </div>
            </div>
            <div id="system-controls-list" class="native-controls-box"></div>
          </div>
        </details>
      </section>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 5: BLE & AREA PRESENCE                                  -->
      <!-- ================================================================== -->
      <section id="view-area_tracking" class="hidden">
        <div class="page-header">
          <h2>BLE &amp; Area Presence</h2>
          <p>Live Area occupancy, weighted BLE + mmWave/PIR sensor fusion, per-area signal calibration, and 1-click Bluetooth device adoption.</p>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px;">
            <div>
              <h3 style="margin:0;">Live Area Presence &amp; Sensor Fusion</h3>
              <p class="desc" style="margin:2px 0 0;">Real-time occupancy (<code>binary_sensor.&lt;area&gt;_ble_occupancy</code> &amp; <code>sensor.&lt;area&gt;_occupants</code>) combining BLE beacons with area occupancy/mmWave/PIR sensors.</p>
            </div>
          </div>
          <div id="area-presence-grid-box" class="native-controls-box"></div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:18px;">
            <div>
              <h3 style="margin:0;">Per-Area BLE Signal Calibration</h3>
              <p class="desc" style="margin:2px 0 0;">Select a BLE-enabled device, carry it into an area, and click <strong>Calibrate Current Area</strong>.</p>
            </div>
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
              <div style="display:flex;align-items:center;gap:8px;">
                <label style="font-size:12px;color:var(--muted);white-space:nowrap;">Calibration Device:</label>
                <select id="ble-survey-device-picker" style="width:auto;min-width:185px;" onchange="onSelectBleSurveyDevice(this.value)"></select>
              </div>
              <label style="font-size:12.5px;font-weight:500;color:var(--accent);display:inline-flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;">
                <input type="checkbox" id="survey-fast-mode" onchange="toggleSurveyFastMode(this.checked)"> Fast Refresh (1.5s)
              </label>
            </div>
          </div>
          <div id="rssi-container"></div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px;">
            <div>
              <h3 style="margin:0;">Discovered Nearby Bluetooth Devices (1-Click Adopt)</h3>
              <p class="desc" style="margin:2px 0 0;">Adopt discovered phones/watches (<code>private_ble_device</code>), iBeacons, or named BLE tags into Latter Area tracking in one click.</p>
            </div>
            <button type="button" class="btn-secondary" style="padding:5px 12px;font-size:12px;" onclick="openAddDeviceModal()">+ Manual BLE Address</button>
          </div>
          <div id="ble-adopt-table-box" class="native-controls-box"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- SYSTEM TAB 6: ADMINISTRATION (BACKUPS, STUDIO, LOGS & DEV YAML)    -->
      <!-- ================================================================== -->
      <section id="view-system_admin" class="hidden">
        <div class="page-header">
          <h2>System Administration</h2>
          <p>Backups, appearance, notification testing, and system logs.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Export Settings (.JSON)</h3>
            <p class="desc">Download a portable JSON bundle of your system settings, entity mappings, BLE area offsets, and live ESPHome device preferences. (Full system backups are handled automatically by Home Assistant's native Backup system.)</p>
            <div class="field">
              <label>Backup Scope</label>
              <select id="bkp-scope-select">
                <option value="system">Full System &amp; All Devices</option>
                <option value="device">Active Device Only</option>
              </select>
            </div>
            <div class="quick-actions-row">
              <button class="btn-primary" onclick="exportBackupToComputer('')">Download .JSON</button>
            </div>
          </div>

          <div class="card">
            <h3>Restore from File (.JSON)</h3>
            <p class="desc">Upload a downloaded <code>latter-*.json</code> backup file from your computer.</p>
            <div class="field">
              <label>Backup .JSON File</label>
              <input type="file" id="bkp-upload-file" accept=".json,application/json">
            </div>
            <div class="toggle-row" style="margin-bottom:12px;">
              <span>Restore Live ESPHome Device Settings</span>
              <input type="checkbox" id="bkp-restore-esp" checked>
            </div>
            <button class="btn-primary" onclick="restoreFromUploadedFile()">Upload &amp; Restore</button>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Reverse Proxy &amp; External Access</h3>
            <p class="desc">Optional external HTTPS base URL override used when linking ESPHome device <em>Visit</em> buttons through a reverse proxy.</p>
            <div class="field">
              <label>Companion Base URL Override (Optional)</label>
              <input type="text" id="cfg-companion_base_url" placeholder="Auto-detected from Home Assistant (e.g. https://ha.example.com)" oninput="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Notification Tester</h3>
            <p class="desc">Send a test on-screen alert (<code>latter.notify</code>) to a specific device.</p>
            <div class="field">
              <label>Target Device</label>
              <select id="test-alert-device"></select>
            </div>
            <div class="form-grid-2" style="margin-bottom:10px;">
              <input type="text" id="test-alert-title" value="Front Door" placeholder="Title">
              <select id="test-alert-prio">
                <option value="normal">Priority: Normal</option>
                <option value="warning">Priority: Warning</option>
                <option value="critical">Priority: Critical</option>
              </select>
            </div>
            <div class="field">
              <input type="text" id="test-alert-msg" value="Person detected at Front Door" placeholder="Message">
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
              <label style="font-size:12.5px;color:var(--muted);display:inline-flex;align-items:center;gap:6px;cursor:pointer;">
                <input type="checkbox" id="test-alert-cam" checked> Include Camera Snapshot
              </label>
              <button class="btn-primary" onclick="sendTestNotification()">Send Notification</button>
            </div>
          </div>
        </div>

        <div class="card" id="sys-custom-palettes-card">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px;">
            <div>
              <h3 style="margin:0;">System Custom Color Library</h3>
              <p class="desc" style="margin:2px 0 0;">Create custom UI color profiles on the HSV Color Wheel and reuse them across any display.</p>
            </div>
            <button type="button" class="btn-secondary" onclick="openColorWheelModal('system')">+ Open Color Wheel</button>
          </div>
          <div id="sys-custom-palettes-list" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;"></div>
        </div>

        <!-- COLLAPSIBLE: SYSTEM & DEVICE LOGS -->
        <details class="ha-details">
          <summary>System &amp; Device Logs</summary>
          <div class="details-body">
            <div class="quick-actions-row" style="margin-bottom:12px;">
              <button type="button" class="btn-secondary" onclick="openNativeHaLogs('latter')">HA Logs (latter)</button>
              <button type="button" class="btn-secondary" id="btn-native-dev-logs" onclick="openNativeHaLogs(STATE?.config?.device_slug || 'esphome')">HA Logs (Active Device)</button>
              <button type="button" class="btn-secondary" onclick="openNativeHaLogs('esphome')">HA Logs (esphome)</button>
              <button type="button" class="btn-secondary" onclick="openNativeHaIntegrations()">HA Integration Page</button>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
              <select id="log-filter-select" style="width:auto;min-width:200px;" onchange="renderLogsView()">
                <option value="all">All Latter &amp; ESPHome Logs</option>
                <option value="device">Active Device Only</option>
                <option value="latter">Latter Middleware Only</option>
                <option value="errors">Warnings &amp; Errors Only</option>
              </select>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <button type="button" class="btn-secondary" onclick="refreshState(false)">Refresh</button>
                <button type="button" class="btn-secondary" onclick="copyTextById('internal-log-output')">Copy</button>
                <button type="button" class="btn-danger" onclick="clearInternalLogs()">Clear</button>
              </div>
            </div>
            <pre id="internal-log-output" class="mono" style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;overflow-x:auto;max-height:380px;margin:0;color:var(--text-strong);line-height:1.5;">No events logged yet.</pre>
          </div>
        </details>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICES LANDING PAGE (CATEGORY DROPDOWN + SORTABLE TABLE)          -->
      <!-- ================================================================== -->
      <section id="view-select_device_prompt" class="hidden">
        <div class="page-header">
          <h2>Devices</h2>
          <p>Select a device to manage its settings, or adopt a Bluetooth phone, watch, or tag.</p>
        </div>
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:220px;max-width:340px;">
              <select id="device-category-filter" onchange="onFilterDeviceCategory(this.value)">
                <option value="all">Category: All Devices</option>
                <option value="online">Online / Active Devices</option>
                <option value="native">Latter Native Devices</option>
                <option value="ble_tracked">BLE Tracked Devices</option>
                <option value="roaming">Roaming Devices</option>
                <option value="stationary">Stationary Devices</option>
                <option value="headless">Screenless / Headless Devices</option>
                <option value="ble_beacon">BLE Phones, Watches &amp; Tags</option>
                <option value="updates">Firmware Updates Available</option>
              </select>
            </div>
            <button type="button" class="btn-primary" id="btn-open-add-device" onclick="openAddDeviceModal()">+ Add Device</button>
          </div>
          <div id="prompt-devices-list"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE TAB 1: OVERVIEW (TELEMETRY, QUICK ACTIONS & DEVICE STATUS)  -->
      <!-- ================================================================== -->
      <section id="view-dashboard">
        <div class="page-header">
          <h2 id="dash-header-title">Overview</h2>
        </div>

        <div class="hero-stats" style="grid-template-columns:repeat(4, minmax(0, 1fr));">
          <div class="stat-box"><span id="st-area-label">Current Area</span><strong id="st-area">--</strong></div>
          <div class="stat-box"><span>Battery / Power</span><strong id="st-battery">--</strong></div>
          <div class="stat-box"><span>Wi-Fi Signal</span><strong id="st-wifi">--</strong></div>
          <div class="stat-box"><span>Firmware Version</span><strong id="st-fw-version">--</strong></div>
        </div>

        <div class="grid-2">
          <!-- CARD 1: QUICK ACTIONS & PROFILE -->
          <div class="card">
            <h3>Quick Actions</h3>
            <p class="desc">Execute immediate device commands or apply a saved configuration profile.</p>
            <div id="dash-quick-actions" class="quick-actions-row" style="margin-bottom:18px;"></div>

            <div class="field hidden" id="dash-power-profile-wrap">
              <label>Sleep &amp; Wake Power Profile</label>
              <select id="dash-power-profile-select" onchange="if (this.dataset.ent) espSelect(this.dataset.ent, this.value)"></select>
            </div>

            <div class="field">
              <label>Apply Configuration Profile</label>
              <div class="input-action-row">
                <select id="quick-profile-select"></select>
                <button class="btn-chip" onclick="applyQuickProfileFromOverview()">Apply Profile</button>
              </div>
            </div>

            <div class="field" id="dash-assigned-person-field" style="padding-top:12px;border-top:1px solid var(--border);">
              <label>Assigned Person (<code>sensor.&lt;person&gt;_current_area</code>)</label>
              <select id="cfg-assigned_person" onchange="onAssignedPersonChanged(this.value)"></select>
            </div>
          </div>

          <!-- CARD 2: DEVICE STATUS & BACKUPS -->
          <div class="card">
            <h3>Device Status</h3>
            <p class="desc">Hardware model, roaming location mode, and device management.</p>
            <div class="summary-row"><span>Hardware Model</span><strong id="dash-hw-model">--</strong></div>
            <div class="summary-row"><span>IP Address</span><strong id="dash-ip-addr">--</strong></div>
            <div class="summary-row"><span>Location Mode</span><strong id="dash-ble-mode">--</strong></div>
            <div class="summary-row" id="dash-row-ble-proxy"><span>Nearest BLE Proxy</span><strong id="dash-ble-proxy">--</strong></div>
            <div class="summary-row"><span>Device Group</span><strong id="st-group">Unassigned</strong></div>
            <div class="quick-actions-row" style="margin-top:16px;">
              <button class="btn-chip" onclick="exportBackupToComputer('device')">Download .JSON</button>
              <button class="btn-chip" onclick="navigateToView('system')">Administration &amp; Logs</button>
            </div>
          </div>
        </div>

        <!-- TIER 3 / SENSOR NODE CONTROLS (SHOWN WHEN CUSTOM/OTHER ENTITIES EXIST) -->
        <div class="card hidden" id="dash-sensor-entities-card">
          <h3>Device Sensors &amp; Controls</h3>
          <p class="desc">Exposed sensors, switches, and parameters on this ESPHome node.</p>
          <div id="dash-device-entities" class="native-controls-box"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE TAB 2: DISPLAY & HOME                                       -->
      <!-- ================================================================== -->
      <section id="view-home_display" class="hidden">
        <div class="page-header">
          <h2>Display &amp; Home</h2>
          <p>Configure screen brightness, color profile, clock face, home dock apps, area UI defaults, and wallpapers.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Display &amp; Appearance</h3>
            <p class="desc">Screen brightness, auto-brightness schedule, clock face, color profile, and weather simulation.</p>
            <div id="embedded-display" class="native-controls-box" style="margin-bottom:14px;"></div>

            <div class="field" style="padding:12px;border-radius:10px;background:var(--input-bg);border:1px solid var(--border);">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <label style="margin-bottom:0;">Custom Color Profile</label>
                <button type="button" class="btn-secondary" style="padding:4px 10px;font-size:12px;" onclick="openColorWheelModal('device')">+ Color Wheel</button>
              </div>
              <div style="display:flex;gap:8px;align-items:center;">
                <span id="dev-color-swatch" style="width:24px;height:24px;border-radius:50%;border:2px solid #fff;background:#3898FF;flex-shrink:0;"></span>
                <select id="dev-custom-palette-select" onchange="onSelectDeviceCustomPalette(this.value)" style="flex:1;"></select>
              </div>
            </div>

            <div class="field">
              <label>Display Geometry &amp; Resolution</label>
              <div class="form-grid-2">
                <select id="cfg-display_shape" onchange="markDirty()">
                  <option value="circle">Circular Display</option>
                  <option value="square">Rectangular / Square</option>
                </select>
                <select id="cfg-art_size" onchange="markDirty()">
                  <option value="466">466x466 px (Pocket Assistant 1.75" Round)</option>
                  <option value="480">480x480 px (Mobile Assistant 2.16" Square)</option>
                  <option value="410x502">410x502 px (Wrist Assist 2.06" Watch)</option>
                  <option value="320x480">320x480 px (Remote Assistant 3.5" P4)</option>
                  <option value="720">720x720 px (Desk Assistant 4.0" P4)</option>
                  <option value="360">360x360 px</option>
                  <option value="240">240x240 px</option>
                </select>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>Home Screen &amp; Area UI</h3>
            <p class="desc">Configure home screen behavior, dock apps, and default Area Control category.</p>
            <div id="embedded-home" class="native-controls-box" style="margin-bottom:14px;"></div>

            <div class="field">
              <label>Home Dock Apps (Click to Enable/Disable, Arrows to Reorder)</label>
              <div id="dock-pills-container" class="dock-pill-list"></div>
              <input type="hidden" id="cfg-dock_apps">
            </div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:18px;">
            <div>
              <h3 style="margin:0;">Wallpapers</h3>
              <p class="desc" style="margin:2px 0 0;">Select an AMOLED preset, upload a custom photo, or star multiple favorites to rotate automatically.</p>
            </div>
            <div class="input-action-row" style="flex:0 1 auto;">
              <select id="cfg-wallpaper_cycle_minutes" style="width:auto;min-width:170px;" title="Favorite Wallpaper Rotation" onchange="markDirty()">
                <option value="0">Rotation: Off</option>
                <option value="15">Rotate: Every 15m</option>
                <option value="60">Rotate: Every Hour</option>
                <option value="360">Rotate: Every 6h</option>
                <option value="1440">Rotate: Daily</option>
              </select>
              <button class="btn-secondary" onclick="selectWallpaperSource('')">Disable Wallpaper</button>
            </div>
          </div>
          <div class="input-action-row" style="padding:10px 12px;background:var(--input-bg);border:1px solid var(--border);border-radius:8px;margin-bottom:12px;">
            <input type="file" id="wp-file-input" accept="image/*">
            <button class="btn-primary" onclick="uploadWallpaperFile()">Upload Photo</button>
            <input type="hidden" id="cfg-wallpaper_source">
          </div>
          <div id="wp-gallery-grid" class="wp-gallery"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE TAB 3: AUDIO & VOICE                                        -->
      <!-- ================================================================== -->
      <section id="view-audio_voice" class="hidden">
        <div class="page-header">
          <h2>Audio &amp; Voice</h2>
          <p>Configure on-device wake words, voice assistant behavior, sound chimes, and Music Assistant library sorting.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Voice Assistant &amp; Wake Word</h3>
            <p class="desc">Configure wake word operating mode, active wake word model, and visual profile.</p>
            <div id="embedded-voice-primary" class="native-controls-box" style="margin-bottom:10px;"></div>

            <div class="toggle-row" id="row-sync-device-area" style="margin-bottom:10px;">
              <span>Voice Follows Me (move this device's Home Assistant Area with it)</span>
              <input type="checkbox" id="cfg-sync_device_area" onchange="markDirty()">
            </div>

            <details class="ha-details" id="details-voice-sens" style="margin-bottom:0;">
              <summary>Wake Word Sensitivity (Per Model)</summary>
              <div class="details-body">
                <div id="embedded-voice-sens" class="native-controls-box"></div>
              </div>
            </details>
          </div>

          <div class="card">
            <h3>Sound &amp; Media Player</h3>
            <p class="desc">Adjust onboard alert volume, volume step size, player appearance, and default speaker.</p>
            <div id="embedded-sound" class="native-controls-box" style="margin-bottom:8px;"></div>
            <div id="embedded-music" class="native-controls-box" style="margin-bottom:12px;"></div>

            <div class="field">
              <label>Default Speaker Entity</label>
              <select id="cfg-default_speaker" onchange="markDirty()"></select>
            </div>
            <div class="toggle-row" style="margin-bottom:10px;">
              <span>Auto-Switch Speaker &amp; Remote on Area Change</span>
              <input type="checkbox" id="cfg-area_handoff" onchange="markDirty()">
            </div>

            <details class="ha-details" style="margin-bottom:0;">
              <summary>Library Sorting Preferences</summary>
              <div class="details-body">
                <div id="embedded-music-sort" class="native-controls-box"></div>
              </div>
            </details>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE TAB 4: POWER & BATTERY                                      -->
      <!-- ================================================================== -->
      <section id="view-power" class="hidden">
        <div class="page-header">
          <h2>Power &amp; Battery</h2>
          <p>Configure screen timeouts, wake gestures, docked screensaver, and view live battery health.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Sleep &amp; Wake Timeouts</h3>
            <p class="desc">Inactivity timeouts, pickup-to-wake, tap-to-wake, docked screensaver, and hardware hibernate.</p>
            <div id="embedded-sleep" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Battery &amp; Power Telemetry</h3>
            <p class="desc">Live battery charge level, charging status, PMIC voltage, and internal temperature.</p>
            <div id="embedded-battery" class="native-controls-box"></div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE TAB 5: ADMINISTRATION (IDENTITY, BLE, RAW, REMOVE)          -->
      <!-- ================================================================== -->
      <section id="view-system" class="hidden">
        <div class="page-header">
          <h2>Device Administration</h2>
          <p>Device identity, BLE area tracking configuration, and entity inspection.</p>
        </div>

        <div class="grid-2">
          <!-- CARD 1: DEVICE IDENTITY -->
          <div class="card">
            <h3>Device Identity</h3>
            <p class="desc">Configure this device's normalized ESPHome slug, hardware type, logical group, and pagination.</p>
            <div class="field">
              <label>ESPHome Device Slug (sensor.&lt;slug&gt;_*)</label>
              <input type="text" id="cfg-device_slug" readonly title="Set from the ESPHome node name when the Device was added">
            </div>
            <div class="field">
              <label>Device Type</label>
              <select id="cfg-device_profile" onchange="markDirty()">
                <option value="mobile_display">Mobile Display</option>
                <option value="wearable_display">Wearable Display</option>
                <option value="stationary_display">Stationary Display</option>
                <option value="headless_node">Headless / Sensor Node</option>
                <option value="ble_beacon">BLE Phone / Watch / Tag</option>
              </select>
            </div>
            <div class="form-grid-2">
              <div class="field">
                <label>Device Group</label>
                <select id="cfg-device_group" onchange="markDirty()"></select>
              </div>
              <div class="field">
                <label>Area Cards Per Page</label>
                <input type="number" id="cfg-default_page_size" min="1" max="20" value="3" oninput="markDirty();">
              </div>
            </div>
          </div>

          <!-- CARD 2: BLE AREA TRACKING -->
          <div class="card">
            <h3>BLE Area Tracking</h3>
            <p class="desc">Configure how this device roams between areas using ESPHome Bluetooth proxies.</p>
            <div class="toggle-row">
              <span>Enable BLE Proxy Area Tracking</span>
              <input type="checkbox" id="cfg-native_ble_tracking" onchange="markDirty()">
            </div>
            <div class="toggle-row" style="margin-bottom:10px;">
              <span>Auto-Switch Active Area on Movement</span>
              <input type="checkbox" id="cfg-ble_auto_switch" onchange="markDirty()">
            </div>
            <div id="embedded-area-ble" class="native-controls-box" style="margin-bottom:12px;"></div>
            <div class="field">
              <label>Default Fallback Area</label>
              <select id="cfg-default_area" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>BLE Target Address / Entity (Optional — MAC or private_ble_device)</label>
              <input type="text" id="cfg-ble_target_address" class="mono" placeholder="Auto-discovered from ESPHome or device_tracker.*" oninput="markDirty()">
            </div>
            <div class="field">
              <label>BLE iBeacon UUID</label>
              <input type="text" id="cfg-ble_beacon_uuid" oninput="markDirty();">
            </div>
            <div class="field">
              <label>External Area Sensor Override (Optional)</label>
              <select id="cfg-presence_entity" onchange="markDirty()"></select>
            </div>
          </div>
        </div>

        <!-- COLLAPSIBLE: DIAGNOSTICS & RAW ENTITY INSPECTOR -->
        <details class="ha-details">
          <summary>Diagnostics &amp; Raw ESPHome Entity Inspector</summary>
          <div class="details-body">
            <div id="embedded-network" class="native-controls-box" style="margin-bottom:12px;"></div>
            <div style="margin-bottom:10px;">
              <input type="text" id="esp-search" placeholder="Filter all entities by name or entity_id..." oninput="renderRawEntityList()">
            </div>
            <div id="raw-entity-items" class="native-controls-box"></div>
          </div>
        </details>

        <!-- DEDICATED REMOVE DEVICE CARD -->
        <div class="card" style="border-color:rgba(219, 68, 55, 0.35);margin-top:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
            <div>
              <h3 style="margin:0;color:var(--danger);">Remove Device</h3>
              <p class="desc" style="margin:2px 0 0;">Remove this device from Latter. The ESPHome device itself will remain in Home Assistant and can be re-added anytime.</p>
            </div>
            <button type="button" class="btn-danger" onclick="removeManagedDevice(STATE.subentry_id, STATE.title)">Remove Device from Latter</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>

<div id="toast" class="toast">Saved</div>

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
let STATE = null;
let CALENDARS = [];
let IS_DIRTY = false;
let INITIAL_FORM_LOADED = false;

let CURRENT_SCOPE = "system";
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
const SYSTEM_WS_COMMANDS = new Set([
  "set_ble_area_offset",
  "set_area_fusion_mode",
  "auto_calibrate_here",
  "system_entity_action",
  "esphome_entity_action",
  "send_test_notification",
  "check_system_updates",
  "log_client_error",
  "clear_internal_logs",
  "remove_device",
  "add_ble_device",
  "set_device_remote_group",
  "create_device_group",
  "delete_device_group",
  "delete_profile",
  "apply_profile",
  "export_backup_json",
  "restore_backup"
]);

const DEVICE_WS_COMMANDS = new Set([
  "test_doorbell_speaker",
  "upload_wallpaper",
  "select_wallpaper",
  "toggle_wallpaper_favorite",
  "delete_wallpaper",
  "save_config",
  "capture_profile"
]);

async function callStudioCommand(bodyObj) {
  if (!HASS_REF) throw new Error("Home Assistant connection not ready");
  const { command, ...payload } = bodyObj || {};
  const cmdName = command || "save_config";
  if (DEVICE_WS_COMMANDS.has(cmdName) && !ACTIVE_SUBENTRY_ID) {
    showToast("Select a device first");
    return null;
  }
  const wsType = DEVICE_WS_COMMANDS.has(cmdName) ? "latter/device/command" : "latter/system/command";
  return await HASS_REF.callWS({
    type: wsType,
    command: cmdName,
    subentry_id: ACTIVE_SUBENTRY_ID || null,
    payload
  });
}

function toggleParentHaSidebar() {
  if (HOST_ELEMENT) {
    HOST_ELEMENT.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }
}

function closeCameraPreviewBox() {
  const box = doc.getElementById("cam-preview-box");
  if (box) box.style.display = "none";
}

function showToast(msg) {
  const t = doc.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 2400);
}

window.addEventListener("error", (ev) => {
  const msg = `${ev.message || "JS Error"} at line ${ev.lineno || "?"}`;
  callStudioCommand({command: "log_client_error", source: "webui_js", message: msg}).catch(() => {});
});

window.addEventListener("unhandledrejection", (ev) => {
  const msg = `Unhandled Promise Rejection: ${ev.reason?.message || ev.reason || "unknown"}`;
  callStudioCommand({command: "log_client_error", source: "webui_promise", message: msg}).catch(() => {});
});

function renderLogsView() {
  const logPre = doc.getElementById("internal-log-output");
  if (!logPre) return;
  const allLogs = STATE?.internal_logs || [];
  const filterMode = doc.getElementById("log-filter-select")?.value || "all";
  const slug = (STATE?.config?.device_slug || "").toLowerCase();
  const slugHyphen = slug.replace(/_/g, "-");

  const devBtn = doc.getElementById("btn-native-dev-logs");
  if (devBtn && slug) {
    devBtn.textContent = `HA Logs (${slug})`;
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
    ? filtered.map(l => `[${l.ts}] [${l.level}] (${l.source}) ${l.message}`).join("\n\n")
    : "No matching log entries.";
}

function openNativeHaLogs(filterTerm) {
  const q = filterTerm ? `?filter=${encodeURIComponent(filterTerm)}` : "";
  const targetPath = `/config/logs${q}`;

  window.open(targetPath, "_blank");
}

function openNativeHaIntegrations() {
  const targetPath = "/config/integrations/integration/latter";

  window.open(targetPath, "_blank");
}

async function clearInternalLogs() {
  const data = await callStudioCommand({command: "clear_internal_logs"});
  if (data) {
    applyStateToDom(data, false);
    showToast("Cleared studio events");
  }
}

function markDirty() {
  IS_DIRTY = true;
  doc.getElementById("dirty-indicator").classList.add("visible");
  const btn = doc.getElementById("btn-save-changes");
  if (btn) {
    btn.disabled = false;
    btn.textContent = "Save Changes";
  }
}

function clearDirty() {
  IS_DIRTY = false;
  doc.getElementById("dirty-indicator").classList.remove("visible");
  const btn = doc.getElementById("btn-save-changes");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saved";
  }
}


const VIEW_TITLES = {
  system_overview: "Overview",
  shared_entities: "Shared Entities",
  remotes: "Media & Remotes",
  system_sync: "Groups & Profiles",
  area_tracking: "BLE Calibration",
  system_admin: "Administration",
  select_device_prompt: "Devices",
  dashboard: "Overview",
  home_display: "Display & Home",
  audio_voice: "Audio & Voice",
  power: "Power & Battery",
  system: "Administration"
};
let CURRENT_VIEW_ID = "dashboard";

function updateUnifiedPageTitle(viewId) {
  if (viewId) CURRENT_VIEW_ID = viewId;
  const titleEl = doc.getElementById("unified-page-title");
  if (!titleEl) return;
  const baseTitle = VIEW_TITLES[CURRENT_VIEW_ID] || "Overview";
  if (CURRENT_SCOPE === "device" && DEVICE_SELECTED && CURRENT_VIEW_ID !== "select_device_prompt") {
    const devTitle = STATE?.esphome?.device?.name || STATE?.title || "Device";
    titleEl.innerHTML = `<span>${esc(baseTitle)}</span><span class="header-device-sub">&mdash; ${esc(devTitle)}</span>`;
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
      updPill.textContent = `Update Available${lat} — Click to Update`;
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
  const data = await callStudioCommand({command: "check_system_updates"});
  if (data) {
    applyStateToDom(data, false);
    showToast("Checked for Latter & device firmware updates");
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
  updateUnifiedPageTitle(viewId);
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
    applyStateToDom(STATE, true);
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
    INITIAL_FORM_LOADED = false;
    await refreshState(true);
    if (HOST_ELEMENT && typeof HOST_ELEMENT._resubscribe === "function") {
      await HOST_ELEMENT._resubscribe(false);
    }
  } else {
    applyStateToDom(STATE, true);
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
  const availDockMeta = DOCK_APP_META.slice();
  const rawTokens = inp.value
    .split(/[,;| ]+/)
    .map(t => {
      const v = t.trim().toLowerCase();
      return v;
    })
    .filter(Boolean);

  const activeTokens = [];
  rawTokens.forEach(t => {
    if (availDockMeta.some(m => m.token === t) && !activeTokens.includes(t)) {
      activeTokens.push(t);
    }
  });
  const disabledTokens = availDockMeta
    .map(m => m.token)
    .filter(t => !activeTokens.includes(t));

  const allOrdered = activeTokens.concat(disabledTokens);
  box.innerHTML = allOrdered.map((tok) => {
    const meta = DOCK_APP_META.find(m => m.token === tok);
    const isEn = activeTokens.includes(tok);
    const actIdx = activeTokens.indexOf(tok);
    const canLeft = isEn && actIdx > 0;
    const canRight = isEn && actIdx < activeTokens.length - 1;
    return `<div class="dock-pill ${isEn ? 'enabled' : ''}" onclick="toggleDockAppToken(${jsArg(tok)})">
      ${canLeft ? `<span class="move-arrow" title="Move Left" onclick="event.stopPropagation(); moveDockAppToken(${jsArg(tok)}, -1)">◀</span>` : ''}
      <span>${isEn ? '✓ ' : '+ '}${esc(meta ? meta.label : tok)}</span>
      ${canRight ? `<span class="move-arrow" title="Move Right" onclick="event.stopPropagation(); moveDockAppToken(${jsArg(tok)}, 1)">▶</span>` : ''}
    </div>`;
  }).join("");
}

function toggleDockAppToken(tok) {
  const inp = doc.getElementById("cfg-dock_apps");
  if (!inp) return;
  let active = inp.value
    .split(/[,;| ]+/)
    .map(t => {
      const v = t.trim().toLowerCase();
      return v;
    })
    .filter(t => DOCK_APP_META.some(m => m.token === t));
  let nowEnabled = true;
  if (active.includes(tok)) {
    if (active.length <= 1) return;
    active = active.filter(t => t !== tok);
    nowEnabled = false;
  } else {
    active.push(tok);
    nowEnabled = true;
  }
  inp.value = active.join(",");
  markDirty();
  renderDockPillsFromInput();

  // Also sync the underlying ESPHome Shortcut switch immediately if present
  const homeItems = getSectionItems("home");
  const matchSw = homeItems.find(it =>
    it.domain === "switch" &&
    `${it.name} ${it.entity_id}`.toLowerCase().includes(`shortcut`) &&
    `${it.name} ${it.entity_id}`.toLowerCase().includes(tok)
  );
  if (matchSw) {
    espAction(matchSw.entity_id, nowEnabled ? "turn_on" : "turn_off");
  }
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
  markDirty();
  renderDockPillsFromInput();
}

function toggleSurveyFastMode(enabled) {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  const intervalMs = enabled ? 1500 : 5000;
  POLL_TIMER = setInterval(() => refreshState(false), intervalMs);
  if (enabled) refreshState(false);
}

function renderRssiBars(surveyRows, packetsSeen) {
  const box = doc.getElementById("rssi-container");
  if (!box) return;
  const rows = surveyRows || [];
  if (!rows.length) {
    box.innerHTML = `<p class="desc">No Bluetooth proxies discovered yet (Packets seen: ${esc(packetsSeen || 0)}).</p>`;
    return;
  }
  box.innerHTML = rows.map(r => {
    const hasSignal = r.raw_rssi !== null && r.raw_rssi !== undefined;
    const eff = hasSignal ? r.effective_rssi : -100;
    const pct = hasSignal ? Math.max(6, Math.min(100, Math.round(((eff + 100) / 55) * 100))) : 0;
    const offSign = r.offset_db > 0 ? `+${r.offset_db}` : `${r.offset_db}`;
    const ageText = hasSignal ? `${r.age_seconds}s ago` : "No signal yet";
    const distText = (hasSignal && r.distance_m != null)
      ? ` &bull; Distance: <strong style="color:var(--text-strong);">~${esc(r.distance_m)}m (${esc(r.distance_ft)}ft)</strong>`
      : "";
    const sigText = hasSignal
      ? `Raw: <strong>${esc(r.raw_rssi)} dBm</strong> &bull; Offset: <strong>${esc(offSign)} dB</strong> &rarr; Effective: <strong style="color:var(--accent);">${esc(r.effective_rssi)} dBm</strong>${distText}`
      : `Offset: <strong>${esc(offSign)} dB</strong> &bull; Waiting for beacon packet...`;
    const winBadge = r.is_winner
      ? `<span class="state-badge" style="border-color:var(--success);color:var(--success);margin-left:6px;">ACTIVE</span>`
      : "";

    return `<div style="background:var(--input-bg);border:1px solid ${r.is_winner ? 'var(--accent)' : 'var(--border)'};border-radius:10px;padding:11px 13px;margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px;">
        <div>
          <strong style="color:var(--text-strong);font-size:13.5px;font-weight:500;">${esc(r.area_name)}</strong>
          <small style="color:var(--muted);margin-left:6px;">(${esc(r.scanner)} &bull; ${esc(ageText)})</small>
          ${winBadge}
        </div>
        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
          <button class="btn-secondary" style="padding:4px 8px;font-size:12px;" onclick="setBleOffset(${jsArg(r.area_id)}, ${Number(r.offset_db) - 1})">-1 dB</button>
          <span class="state-badge" style="min-width:52px;text-align:center;">${esc(offSign)} dB</span>
          <button class="btn-secondary" style="padding:4px 8px;font-size:12px;" onclick="setBleOffset(${jsArg(r.area_id)}, ${Number(r.offset_db) + 1})">+1 dB</button>
          ${r.offset_db !== 0 ? `<button class="btn-danger" style="padding:4px 7px;font-size:11.5px;" title="Reset to 0 dB" onclick="setBleOffset(${jsArg(r.area_id)}, 0)">0</button>` : ''}
          <button class="btn-secondary" style="padding:4px 10px;font-size:12px;border-color:var(--accent);color:var(--accent);" onclick="autoCalibrateHere(${jsArg(r.area_id)})">Calibrate Current Area</button>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px;">${sigText}</div>
      <div class="rssi-track"><div class="rssi-fill" style="width:${pct}%;opacity:${hasSignal ? 1 : 0.2};"></div></div>
    </div>`;
  }).join("");
}

function renderSystemOverview(systemDevices, systemControls, cfg) {
  const countBadge = doc.getElementById("nav-system-count");
  if (countBadge) countBadge.textContent = String((systemDevices || []).length);

  const groups = STATE?.device_groups || [];
  const profiles = STATE?.saved_profiles || [];
  const live = STATE?.live || {};

  const profDevLbl = doc.getElementById("prof-active-dev-label");
  if (profDevLbl) profDevLbl.textContent = STATE?.title || cfg?.device_slug || "Active Device";

  const picker = doc.getElementById("system-device-picker");
  if (picker && systemDevices) {
    const placeholder = `<option value="" ${!DEVICE_SELECTED ? 'selected' : ''}>— Select a Device —</option>`;
    picker.innerHTML = placeholder + systemDevices.map(d =>
      `<option value="${esc(d.subentry_id || d.entry_id)}" ${(DEVICE_SELECTED && d.is_current) ? 'selected' : ''}>${esc(d.title)}</option>`
    ).join("");
  }

  const quickProfSel = doc.getElementById("quick-profile-select");
  if (quickProfSel && profiles.length) {
    const prevP = quickProfSel.value;
    quickProfSel.innerHTML = profiles.map(p =>
      `<option value="${esc(p.id)}" ${p.id === prevP ? 'selected' : ''}>${esc(p.name)}</option>`
    ).join("");
  }

  const devGrpSel = doc.getElementById("cfg-device_group");
  if (devGrpSel && groups.length) {
    const curGrp = cfg?.device_group || "handhelds";
    devGrpSel.innerHTML = groups.map(g =>
      `<option value="${esc(g.id)}" ${g.id === curGrp ? 'selected' : ''}>Group: ${esc(g.name)}</option>`
    ).join("");
  }

  const targetScopes = [
    {id: "current", name: `Current Device (${STATE?.title || cfg?.device_slug || 'Active'})`},
    {id: "all", name: `All Devices (${(systemDevices || []).length})`}
  ];
  groups.forEach(g => {
    const cnt = (systemDevices || []).filter(d => d.device_group === g.id).length;
    targetScopes.push({id: `group:${g.id}`, name: `Group: ${g.name} (${cnt})`});
  });
  (systemDevices || []).forEach(d => {
    targetScopes.push({id: `device:${d.subentry_id}`, name: `Device: ${d.title}`});
  });

  const profScopeSel = doc.getElementById("profile-target-scope");
  if (profScopeSel) {
    const prevVal = profScopeSel.value || "current";
    profScopeSel.innerHTML = targetScopes.map(o =>
      `<option value="${esc(o.id)}" ${o.id === prevVal ? 'selected' : ''}>${esc(o.name)}</option>`
    ).join("");
  }

  const grpFilterSel = doc.getElementById("group-ctrl-filter");
  let activeFilter = "all";
  if (grpFilterSel) {
    activeFilter = grpFilterSel.value || "all";
    const filterOpts = [
      {id: "all", name: `Target: All Devices (${(systemDevices || []).length})`}
    ];
    groups.forEach(g => {
      const cnt = (systemDevices || []).filter(d => d.device_group === g.id).length;
      filterOpts.push({id: `group:${g.id}`, name: `Group: ${g.name} (${cnt})`});
    });
    filterOpts.push({id: "arch:mobile_display", name: "Type: Mobile Displays"});
    filterOpts.push({id: "arch:stationary_display", name: "Type: Stationary Displays"});
    grpFilterSel.innerHTML = filterOpts.map(o =>
      `<option value="${esc(o.id)}" ${o.id === activeFilter ? 'selected' : ''}>${esc(o.name)}</option>`
    ).join("");
  }

  const statusRank = (st) => {
    if (st === "Update Available") return 1;
    if (st === "Offline") return 2;
    return 3;
  };

  const catSel = doc.getElementById("device-category-filter");
  if (catSel) {
    const baseOpts = [
      {id: "all", label: "Category: All Devices"},
      {id: "online", label: "Online / Active Devices"},
      {id: "native", label: "Latter Native Devices"},
      {id: "ble_tracked", label: "BLE Tracked Devices"},
      {id: "roaming", label: "Roaming Devices"},
      {id: "stationary", label: "Stationary Devices"},
      {id: "headless", label: "Screenless / Headless Devices"},
      {id: "ble_beacon", label: "BLE Phones, Watches & Tags"},
      {id: "updates", label: "Firmware Updates Available"}
    ];
    groups.forEach(g => {
      if (g && g.id && g.id !== "unassigned") {
        baseOpts.push({id: `group:${g.id}`, label: `Group: ${g.name}`});
      }
    });
    catSel.innerHTML = baseOpts.map(o =>
      `<option value="${esc(o.id)}" ${o.id === DEVICE_CATEGORY_FILTER ? 'selected' : ''}>${esc(o.label)}</option>`
    ).join("");
  }
  const cat = DEVICE_CATEGORY_FILTER || "all";
  const filteredDevices = (systemDevices || []).filter(d => {
    const isNative = !!d.is_latter_native;
    const isBleTracked = !!(d.has_ble || d.device_profile === "ble_beacon" || (d.area_label || "Roaming") === "Roaming");
    const isRoaming = (d.area_label || "Roaming") === "Roaming";
    if (cat === "online") return d.status_label !== "Offline";
    if (cat === "native") return isNative;
    if (cat === "ble_tracked") return isBleTracked;
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "headless") return d.device_profile === "headless_node" || d.device_profile === "ble_beacon";
    if (cat === "ble_beacon") return d.device_profile === "ble_beacon";
    if (cat === "updates") return d.status_label === "Update Available";
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
      cmp = (a.area_label || "Roaming").localeCompare(b.area_label || "Roaming");
    } else if (DEVICE_SORT_COL === "group") {
      cmp = (a.device_group_name || "Unassigned").localeCompare(b.device_group_name || "Unassigned");
    } else {
      cmp = (a.title || "").localeCompare(b.title || "");
    }
    return DEVICE_SORT_ASC ? cmp : -cmp;
  });

  const sortArrow = (col) => {
    if (DEVICE_SORT_COL !== col) return "";
    return DEVICE_SORT_ASC ? " ▲" : " ▼";
  };

  const thClass = (col) => DEVICE_SORT_COL === col ? "sorted" : "";

  const tableRowsHtml = filteredDevices.map(d => {
    const actAction = d.is_current
      ? `selectCurrentDevice()`
      : `switchSystemDevice(${jsArg(d.subentry_id || d.entry_id)})`;
    const st = d.status_label || "Online";
    const dotCls = st === "Update Available" ? "update" : (st === "Offline" ? "offline" : "online");
    const areaVal = d.area_label || "Roaming";
    const grpVal = d.device_group_name || "Unassigned";
    const mdlVal = d.model_label || "ESPHome Node";
    return `<tr onclick="${actAction}">
      <td class="col-name">${esc(d.title)}</td>
      <td>${esc(mdlVal)}</td>
      <td>${esc(areaVal)}</td>
      <td>${esc(grpVal)}</td>
      <td><span class="status-dot ${dotCls}"></span>${esc(st)}</td>
      <td style="text-align:right;color:var(--muted);font-size:16px;">›</td>
    </tr>`;
  }).join("");

  const tableHtml = filteredDevices.length
    ? `<div class="ha-table-wrap">
        <table class="ha-data-table">
          <thead>
            <tr>
              <th class="${thClass('title')}" onclick="toggleDeviceTableSort('title')">Device${sortArrow('title')}</th>
              <th class="${thClass('model')}" onclick="toggleDeviceTableSort('model')">Model${sortArrow('model')}</th>
              <th class="${thClass('area')}" onclick="toggleDeviceTableSort('area')">Area${sortArrow('area')}</th>
              <th class="${thClass('group')}" onclick="toggleDeviceTableSort('group')">Group${sortArrow('group')}</th>
              <th class="${thClass('status')}" onclick="toggleDeviceTableSort('status')">Status${sortArrow('status')}</th>
              <th style="width:32px;"></th>
            </tr>
          </thead>
          <tbody>${tableRowsHtml}</tbody>
        </table>
      </div>`
    : `<p class="desc" style="margin:8px 0 0;">No matching devices found.</p>`;

  const promptBox = doc.getElementById("prompt-devices-list");
  if (promptBox) promptBox.innerHTML = tableHtml;

  // Populate System -> Overview stats
  const allDevs = systemDevices || [];
  const totalDevs = allDevs.length;
  const onlineDevs = allDevs.filter(d => d.status_label !== "Offline").length;
  const nativeDevs = allDevs.filter(d => d.is_latter_native).length;
  const bleTrackedDevs = allDevs.filter(d => d.has_ble || d.device_profile === "ble_beacon" || (d.area_label || "Roaming") === "Roaming").length;
  const scannersMap = STATE?.live?.ble_scanners_map || {};
  const proxyCount = Object.keys(scannersMap).length || (STATE?.live?.ble_survey_rows || []).length;
  const peopleCount = (STATE?.catalog?.persons || []).length;

  const setSysTxt = (id, val) => {
    const el = doc.getElementById(id);
    if (el) el.textContent = String(val);
  };

  const sysVerClean = String(STATE?.version || "2.2.0").replace(/^v/i, "");
  setSysTxt("sys-sum-version", `v${sysVerClean}`);
  setSysTxt("sys-sum-online", `${onlineDevs} / ${totalDevs}`);
  setSysTxt("sys-sum-native", nativeDevs);
  setSysTxt("sys-sum-ble-tracked", bleTrackedDevs);
  setSysTxt("sys-sum-people", peopleCount);
  setSysTxt("sys-sum-proxies", proxyCount);

  const remCnt = Array.isArray(cfg?.remotes_list) ? cfg.remotes_list.filter(Boolean).length : 0;
  const volCnt = Array.isArray(cfg?.volume_overrides) ? cfg.volume_overrides.length : 0;
  const camCnt = Array.isArray(cfg?.camera_entities) ? cfg.camera_entities.filter(Boolean).length : (cfg?.camera_entity ? 1 : 0);
  const calCnt = Array.isArray(cfg?.calendar_entities) ? cfg.calendar_entities.filter(Boolean).length : 0;

  setSysTxt("sys-sum-remotes", remCnt);
  setSysTxt("sys-sum-vol", volCnt);
  setSysTxt("sys-sum-cameras", camCnt);
  setSysTxt("sys-sum-calendars", calCnt);
  setSysTxt("sys-sum-groups-profiles", `${groups.length} groups / ${profiles.length} profiles`);

  const alertDevSel = doc.getElementById("test-alert-device");
  if (alertDevSel && systemDevices && systemDevices.length) {
    const prevTarget = alertDevSel.value || (STATE?.config?.device_slug || systemDevices[0].device_slug);
    const devOpts = systemDevices.map(d =>
      `<option value="${esc(d.device_slug)}" ${d.device_slug === prevTarget ? 'selected' : ''}>${esc(d.title)} (${esc(d.device_slug)})</option>`
    );
    if (systemDevices.length > 1) {
      devOpts.push(`<option value="follow_me" ${prevTarget === 'follow_me' ? 'selected' : ''}>Follow-Me (Occupied Areas Only)</option>`);
      devOpts.push(`<option value="all" ${prevTarget === 'all' ? 'selected' : ''}>All Devices (${systemDevices.length})</option>`);
    } else {
      devOpts.push(`<option value="follow_me" ${prevTarget === 'follow_me' ? 'selected' : ''}>Follow-Me (Occupied Areas Only)</option>`);
    }
    alertDevSel.innerHTML = devOpts.join("");
  }

  const profBox = doc.getElementById("saved-profiles-list");
  if (profBox) {
    if (!profiles.length) {
      profBox.innerHTML = `<p class="desc">No profiles saved yet.</p>`;
    } else {
      profBox.innerHTML = profiles.map(p => {
        const ctrlCnt = Object.keys(p.esphome_controls || {}).length;
        const isBuiltin = String(p.id || "").startsWith("preset_");
        return `<div class="native-ctrl-row">
          <div class="lbl">
            ${esc(p.name)} <span class="state-badge" style="margin-left:6px;">${ctrlCnt} controls</span>
            <small>${esc(p.description || '')}</small>
          </div>
          <div class="widget">
            <button class="btn-primary" onclick="applySavedProfile(${jsArg(p.id)})">Apply</button>
            ${!isBuiltin ? `<button class="btn-danger" onclick="deleteSavedProfile(${jsArg(p.id)})">✕</button>` : ''}
          </div>
        </div>`;
      }).join("");
    }
  }

  const grpBox = doc.getElementById("device-groups-list");
  if (grpBox) {
    grpBox.innerHTML = groups.map(g => {
      const members = (systemDevices || []).filter(d => d.device_group === g.id);
      const memNames = members.length ? members.map(m => m.title).join(", ") : "None";
      const isDefault = ["unassigned", "handhelds", "bedrooms", "common_areas", "wall_panels", "sensors"].includes(g.id);
      return `<div class="native-ctrl-row">
        <div class="lbl">
          ${esc(g.name)} <span class="state-badge" style="margin-left:6px;">${members.length}</span>
          <small>${esc(g.description || '')} &bull; Devices: <strong>${esc(memNames)}</strong></small>
        </div>
        <div class="widget">
          ${!isDefault ? `<button class="btn-danger" onclick="deleteDeviceGroup(${jsArg(g.id)})">✕</button>` : ''}
        </div>
      </div>`;
    }).join("");
  }

  const fBox = doc.getElementById("system-controls-list");
  if (fBox) {
    if (!systemControls || !systemControls.length) {
      fBox.innerHTML = `<p class="desc">No shared ESPHome controls discovered.</p>`;
    } else {
      const activeCat = doc.getElementById("group-ctrl-cat-filter")?.value || "display";
      const filteredRows = systemControls.map(fc => {
        if (activeCat !== "all" && fc.section !== activeCat) return "";
        const matchingTargets = (fc.targets || []).filter(t => {
          if (activeFilter === "all") return true;
          if (activeFilter.startsWith("group:")) return t.device_group === activeFilter.split(":")[1];
          if (activeFilter.startsWith("arch:")) return t.device_profile === activeFilter.split(":")[1];
          return true;
        });
        if (!matchingTargets.length) return "";
        const entIdsArg = jsArg(matchingTargets.map(t => t.entity_id));
        const devCount = matchingTargets.length;
        const curState = matchingTargets[0].state ?? fc.state;
        let widget = `<span class="state-badge">${esc(curState)}</span>`;
        if (fc.domain === "select" && fc.options && fc.options.length) {
          const opts = fc.options.map(o => `<option value="${esc(o)}" ${o===curState?'selected':''}>${esc(o)}</option>`).join("");
          widget = `<select onchange="bulkSelect(${entIdsArg}, this.value)">${opts}</select>`;
        } else if (fc.domain === "switch") {
          const isOn = curState === "on";
          widget = `<button class="${isOn ? 'btn-primary' : 'btn-secondary'}" onclick="bulkToggle(${entIdsArg}, ${jsArg(isOn ? 'turn_off' : 'turn_on')})">${isOn ? 'ON' : 'OFF'}</button>`;
        } else if (fc.domain === "number") {
          const minV = fc.min ?? 0;
          const maxV = fc.max ?? 100;
          const stepV = fc.step ?? 1;
          const numVal = parseFloat(curState) || 0;
          widget = `<input type="range" min="${esc(minV)}" max="${esc(maxV)}" step="${esc(stepV)}" value="${esc(numVal)}" onchange="bulkNumber(${entIdsArg}, this.value)"><span class="state-badge">${esc(curState)} ${esc(fc.unit || '')}</span>`;
        }
        return `<div class="native-ctrl-row">
          <div class="lbl">
            ${esc(fc.name)}
            <small>${esc(fc.section_title)} &bull; ${devCount} device${devCount > 1 ? 's' : ''}</small>
          </div>
          <div class="widget">${widget}</div>
        </div>`;
      }).filter(Boolean).join("");
      fBox.innerHTML = filteredRows || `<p class="desc">No devices match the selected group filter.</p>`;
    }
  }

  (void 0);
}

async function applyQuickProfileFromOverview() {
  const sel = doc.getElementById("quick-profile-select");
  if (!sel || !sel.value) return;
  const data = await callStudioCommand({command: "apply_profile", profile_id: sel.value, target_scope: "current"});
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
  const rows = STATE?.live?.area_presence_grid || [];
  if (!rows.length) {
    box.innerHTML = `<p class="desc" style="margin:0;">No BLE proxies or area occupancy sensors discovered yet.</p>`;
    return;
  }

  const modeOptions = [
    {val: "weighted", label: "Weighted (BLE + Sensors)"},
    {val: "any_or",     label: "Deterministic OR (BLE or Sensor)"},
    {val: "ble_only",   label: "BLE Only"},
    {val: "ble_and_sensor", label: "Strict AND (BLE + Sensor)"}
  ];

  box.innerHTML = rows.map(r => {
    const isOcc = !!r.is_occupied;
    const occNames = (r.occupant_names && r.occupant_names.length)
      ? r.occupant_names.join(", ")
      : (isOcc ? "Occupied (Sensor)" : "Empty");
    const badgeStyle = isOcc
      ? "background:rgba(46,204,113,0.18);color:var(--ok);border-color:rgba(46,204,113,0.4);"
      : "opacity:0.75;";
    const badgeTxt = isOcc ? `OCCUPIED • ${r.confidence_pct}%` : "CLEAR";
    const sigParts = [];
    if (r.winning_rssi !== null && r.winning_rssi !== undefined) {
      const distTxt = r.closest_distance_ft ? ` (~${r.closest_distance_ft} ft)` : "";
      sigParts.push(`BLE: ${r.winning_rssi} dBm${distTxt}`);
    }
    if (r.active_sensors && r.active_sensors.length) {
      sigParts.push(`Active Sensors: ${r.active_sensors.length}`);
    } else if (r.available_sensors && r.available_sensors.length) {
      sigParts.push(`${r.available_sensors.length} Area Sensor${r.available_sensors.length > 1 ? 's' : ''} (Clear)`);
    }
    if (r.floor_id) {
      sigParts.push(`Floor: ${r.floor_id}`);
    }
    const subTxt = sigParts.length ? sigParts.join(" • ") : "BLE Proxy Ready";
    const curMode = r.fusion_mode || "weighted";
    const optsHtml = modeOptions.map(m =>
      `<option value="${esc(m.val)}" ${m.val === curMode ? 'selected' : ''}>${esc(m.label)}</option>`
    ).join("");

    return `<div class="native-ctrl-row">
      <div class="lbl">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <strong>${esc(r.area_name)}</strong>
          <span class="state-badge" style="${badgeStyle}">${esc(badgeTxt)}</span>
          <span style="font-size:12.5px;color:var(--text-strong);font-weight:500;">${esc(occNames)}</span>
        </div>
        <small>${esc(subTxt)}</small>
      </div>
      <div class="widget">
        <select style="width:auto;min-width:210px;" onchange="setAreaFusionMode(${jsArg(r.area_id)}, this.value)">${optsHtml}</select>
      </div>
    </div>`;
  }).join("");
}

async function setAreaFusionMode(areaId, mode) {
  const data = await callStudioCommand({command: "set_area_fusion_mode", area_id: areaId, mode});
  if (data) {
    applyStateToDom(data, false);
    showToast("Updated Area sensor fusion mode");
  }
}

function renderDiscoveredBleTable() {
  const box = doc.getElementById("ble-adopt-table-box");
  if (!box) return;
  const cands = STATE?.discovered_ble_devices || [];
  if (!cands.length) {
    box.innerHTML = `<p class="desc" style="margin:0;">All discovered Private BLE and named Bluetooth devices are already adopted, or no additional nearby beacons were detected.</p>`;
    return;
  }

  const persons = STATE?.catalog?.persons || [];
  box.innerHTML = cands.map((c, idx) => {
    const pOpts = [`<option value="">— Unassigned Person —</option>`].concat(
      persons.map(p => `<option value="${esc(p.id)}">${esc(p.friendly || p.name)}</option>`)
    ).join("");
    const metaParts = [c.kind || "BLE Device", c.target_address];
    if (c.rssi !== null && c.rssi !== undefined) metaParts.push(`${c.rssi} dBm`);
    if (c.area_name) metaParts.push(`Nearest Area: ${c.area_name}`);

    return `<div class="native-ctrl-row">
      <div class="lbl">
        <strong>${esc(c.title)}</strong>
        <small>${esc(metaParts.join(" • "))}</small>
      </div>
      <div class="widget" style="gap:8px;flex-wrap:wrap;">
        <select id="ble-adopt-person-${idx}" style="width:auto;min-width:165px;">${pOpts}</select>
        <button type="button" class="btn-primary" style="padding:5px 12px;font-size:12px;" onclick="quickAdoptBleCandidate(${idx})">+ Adopt</button>
      </div>
    </div>`;
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
    showToast("Select the BLE survey device first");
    return;
  }
  let data;
  try {
    data = await callStudioCommand({
      command: "auto_calibrate_here",
      area_id: areaId,
      survey_subentry_id: SELECTED_SURVEY_ID
    });
  } catch (err) {
    showToast(`Calibration failed: ${err?.message || err}`);
    return;
  }
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
    box.style.display = "none";
    return;
  }
  const camObj = (STATE?.catalog?.cameras || []).find(c => c.id === camEntityId);
  if (!camObj || !camObj.preview_url) {
    box.style.display = "none";
    showToast("Save configuration first to preview this camera");
    return;
  }
  PREVIEW_CAMERA_ENTITY = camEntityId;
  if (lbl) lbl.textContent = `Preview: ${camEntityId}`;
  img.src = camObj.preview_url;
  box.style.display = "flex";
}

function refreshActiveCameraPreview() {
  if (PREVIEW_CAMERA_ENTITY) {
    renderCameraPreview(PREVIEW_CAMERA_ENTITY);
  }
}

async function testDoorbellSpeaker() {
  const firstCam = doc.querySelector("#cameras-list .cam-ent-sel")?.value || STATE?.config?.camera_entity || "";
  if (!firstCam) {
    showToast("Add a camera entity first");
    return;
  }
  const data = await callStudioCommand({
      command: "test_doorbell_speaker",
      camera_entity: firstCam,
      message: "Hello! Please leave the package by the front door."
    });
  if (data) {
    applyStateToDom(data, false);
    showToast(`Sent test message to ${firstCam} speaker`);
  }
}

async function sendTestNotification() {
  const target_device = doc.getElementById("test-alert-device")?.value || STATE?.config?.device_slug || "";
  const title = doc.getElementById("test-alert-title").value.trim() || "Alert";
  const message = doc.getElementById("test-alert-msg").value.trim() || "Test notification";
  const priority = doc.getElementById("test-alert-prio").value;
  const include_camera = doc.getElementById("test-alert-cam").checked;
  const data = await callStudioCommand({
      command: "send_test_notification",
      target_device,
      title,
      message,
      priority,
      include_camera
    });
  if (data) {
    applyStateToDom(data, false);
    showToast(`Sent notification to ${target_device}`);
  }
}

function renderNativeControlRow(item, showEntityId=false) {
  const stateText = `${item.state}${item.unit ? ' ' + item.unit : ''}`;
  let widgetHtml = `<span class="state-badge">${esc(stateText)}</span>`;

  if (item.domain === "button") {
    widgetHtml = `<button class="btn-secondary" style="padding:5px 12px;font-size:12px;" onclick="espAction(${jsArg(item.entity_id)}, 'press')">Run</button>`;
  } else if (item.domain === "update") {
    const hasUpd = item.state === "on";
    widgetHtml = hasUpd
      ? `<button class="btn-primary" style="padding:5px 12px;font-size:12px;" onclick="espAction(${jsArg(item.entity_id)}, 'install')">Install Update</button>`
      : `<span class="state-badge">Up to date</span><button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="espAction(${jsArg(item.entity_id)}, 'check')">Check</button>`;
  } else if (item.domain === "switch" || item.domain === "light" || item.domain === "fan") {
    const isOn = item.state === "on";
    widgetHtml = `<button class="${isOn ? 'btn-primary' : 'btn-secondary'}" style="padding:5px 12px;font-size:12px;" onclick="espAction(${jsArg(item.entity_id)}, 'toggle')">${isOn ? 'ON' : 'OFF'}</button>`;
  } else if (item.domain === "select" && item.options && item.options.length) {
    const opts = item.options.map(o => `<option value="${esc(o)}" ${o===item.state?'selected':''}>${esc(o)}</option>`).join("");
    widgetHtml = `<select onchange="espSelect(${jsArg(item.entity_id)}, this.value)">${opts}</select>`;
  } else if (item.domain === "number") {
    const minV = item.min ?? 0;
    const maxV = item.max ?? 100;
    const stepV = item.step ?? 1;
    const numVal = parseFloat(item.state) || 0;
    widgetHtml = `
      <input type="range" min="${esc(minV)}" max="${esc(maxV)}" step="${esc(stepV)}" value="${esc(numVal)}" onchange="espNumber(${jsArg(item.entity_id)}, this.value)">
      <span class="state-badge">${esc(stateText)}</span>
    `;
  }

  return `<div class="native-ctrl-row">
    <div class="lbl">
      ${esc(item.name)}
      ${showEntityId ? `<small>${esc(item.entity_id)}</small>` : ''}
    </div>
    <div class="widget">${widgetHtml}</div>
  </div>`;
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
    else if (!low.includes("handoff")) areaBleItems.push(it);
  });
  doc.getElementById("embedded-area-ble").innerHTML = areaBleItems.map(it => renderNativeControlRow(it)).join("");

  // 2. Home Screen & Area UI: Filter out the 6 redundant "Shortcut *" switches (handled by Home Dock App pills)
  const rawHomeItems = getSectionItems("home").filter(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
    return !low.includes("shortcut");
  });
  const homeItems = sortByOrder(rawHomeItems.concat(areaUiItems), [
    "wake greeting", "weather background", "default category", "show all category"
  ]);
  doc.getElementById("embedded-home").innerHTML = homeItems.length
    ? homeItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No on-device Home Screen entities exposed.</p>`;

  // 3. Display & Appearance: Logical order + Conditional Brightness visibility based on Auto Brightness Mode
  const rawDispItems = getSectionItems("display");
  const abModeItem = rawDispItems.find(it => `${it.name} ${it.entity_id}`.toLowerCase().includes("auto_brightness") || (it.name || "").toLowerCase().includes("auto brightness"));
  const abMode = abModeItem ? String(abModeItem.state) : "Sun Synchronized";

  const filteredDisp = rawDispItems.filter(it => {
    const low = `${it.name} ${it.entity_id}`.toLowerCase();
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
    "day start hour", "night start hour", "condition simulation"
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
    : `<p class="desc">No on-device Sleep &amp; Wake entities exposed.</p>`;

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
    : `<p class="desc">No on-device Voice Assistant entities exposed.</p>`;
  doc.getElementById("embedded-voice-sens").innerHTML = voiceSens.length
    ? voiceSens.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No per-model sensitivity controls exposed.</p>`;
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
          `<button class="btn-chip" onclick="espAction(${jsArg(it.entity_id)}, 'press')">${esc(it.name)}</button>`
        ).join("")
      : `<span style="color:var(--muted);font-size:12.5px;">No quick action buttons exposed by this device.</span>`;
  }

  const batItems = getSectionItems("battery");
  doc.getElementById("embedded-battery").innerHTML = batItems.length
    ? batItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No battery telemetry entities reported.</p>`;

  const netItems = getSectionItems("network");
  doc.getElementById("embedded-network").innerHTML = netItems.length
    ? netItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No network or diagnostic entities reported.</p>`;

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
  box.innerHTML = (wallpapers || []).map(wp => {
    const thumbUrl = wp.thumb_url || "";
    const starLabel = wp.favorite ? "★ Fav" : "☆ Fav";
    const delBtn = wp.deletable
      ? `<button class="btn-danger" style="padding:5px 8px;" onclick="deleteWallpaper(${jsArg(wp.id)})">✕</button>`
      : "";
    return `<div class="wp-card ${wp.active ? 'active' : ''}">
      <img class="wp-thumb ${shapeClass}" src="${esc(thumbUrl)}" loading="lazy" alt="${esc(wp.name)}">
      <div class="wp-title">${esc(wp.name)}</div>
      <div class="wp-actions">
        <button class="${wp.active ? 'btn-primary' : 'btn-secondary'}" style="padding:5px 10px;font-size:12px;" onclick="selectWallpaperSource(${jsArg(wp.id)})">${wp.active ? 'Active' : 'Use'}</button>
        <button class="${wp.favorite ? 'btn-primary' : 'btn-secondary'}" style="padding:5px 10px;font-size:12px;" onclick="toggleWallpaperFav(${jsArg(wp.id)})">${starLabel}</button>
        ${delBtn}
      </div>
    </div>`;
  }).join("");
}

async function uploadWallpaperFile() {
  const input = doc.getElementById("wp-file-input");
  if (!input.files || !input.files.length) {
    showToast("Select an image file first");
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
  doc.getElementById("cfg-wallpaper_source").value = sourceId;
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
    showToast("Maximum of 10 cameras reached");
    return;
  }
  const row = document.createElement("div");
  row.className = "native-ctrl-row camera-row-item";
  row.style.marginBottom = "8px";
  const camOptions = (STATE?.catalog?.cameras || []).map(c =>
    `<option value="${esc(c.id)}" ${c.id === entityId ? 'selected' : ''}>${esc(c.name)}</option>`
  ).join("");
  const slotTitle = existingCount === 0
    ? "Camera 1 (Primary / Default Notification Camera)"
    : `Camera ${existingCount + 1}`;
  row.innerHTML = `
    <div style="flex:1;min-width:0;">
      <small class="cam-slot-lbl" style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;font-weight:500;">${esc(slotTitle)}</small>
      <select class="cam-ent-sel" style="width:100%;max-width:none;" onchange="markDirty()"><option value="">— Select Camera —</option>${camOptions}</select>
    </div>
    <div style="display:flex;gap:6px;align-items:center;">
      <button type="button" class="btn-secondary" style="padding:6px 10px;font-size:12px;" onclick="renderCameraPreview(this.parentElement.parentElement.querySelector('.cam-ent-sel').value)">Preview</button>
      <button type="button" class="btn-danger" title="Remove Camera" onclick="this.parentElement.parentElement.remove(); renumberCameraRows(); markDirty();">✕</button>
    </div>
  `;
  list.appendChild(row);
}

function addCalendarRow(entityId="") {
  const list = doc.getElementById("calendars-list");
  if (!list) return;
  const row = document.createElement("div");
  row.className = "native-ctrl-row calendar-row-item";
  row.style.marginBottom = "8px";
  const calOptions = (STATE?.catalog?.calendars || []).map(c =>
    `<option value="${esc(c.id)}" ${c.id === entityId ? 'selected' : ''}>${esc(c.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div style="flex:1;min-width:0;">
      <select class="cal-ent-sel" style="width:100%;max-width:none;" onchange="markDirty()"><option value="">— Select Calendar —</option>${calOptions}</select>
    </div>
    <button type="button" class="btn-danger" title="Remove Calendar" onclick="this.parentElement.remove(); markDirty();">✕</button>
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
    box.innerHTML = `<p style="color:var(--muted);font-size:13px;margin:0 0 10px;">No Remote Groups created yet. Click <strong>+ Create Remote Group</strong> to group remotes by Area.</p>`;
  } else {
    box.innerHTML = REMOTE_GROUPS_STATE.map((grp, gIdx) => {
      const areaOpts = [`<option value="">— No Area (Static Device Assignment Only) —</option>`].concat(
        areas.map(a => `<option value="${esc(a.id)}" ${a.id === grp.area_id ? 'selected' : ''}>Area: ${esc(a.name)}</option>`)
      ).join("");
      const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
      const orderedPool = selectedRems.filter(id => invIds.includes(id)).concat(invIds.filter(id => !selectedRems.includes(id)));
      const pillsHtml = orderedPool.length
        ? orderedPool.map(entId => {
            const isEn = selectedRems.includes(entId);
            const pos = selectedRems.indexOf(entId);
            const badge = isEn ? (pos === 0 ? "★ Primary: " : `#${pos + 1}: `) : "+ ";
            return `<div class="dock-pill ${isEn ? 'enabled' : ''}" onclick="toggleRemoteInGroup(${gIdx}, ${jsArg(entId)})">
              <span>${esc(badge)}${esc(getRemoteFriendlyLabel(entId))}</span>
            </div>`;
          }).join("")
        : `<span style="color:var(--muted);font-size:12px;">Add remotes to the System Remote Inventory above first.</span>`;

      return `<div style="background:var(--input-bg);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px;">
        <div class="form-grid-2" style="margin-bottom:10px;">
          <div>
            <small style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;">Group Name</small>
            <input type="text" value="${esc(grp.name || '')}" placeholder="e.g. Living Room AV" oninput="updateRemoteGroupField(${gIdx}, 'name', this.value)">
          </div>
          <div style="display:flex;gap:8px;align-items:flex-end;">
            <div style="flex:1;">
              <small style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;">Assigned Area (Auto-Loads When Device Enters Area)</small>
              <select onchange="updateRemoteGroupField(${gIdx}, 'area_id', this.value)">${areaOpts}</select>
            </div>
            <button type="button" class="btn-danger" title="Delete Remote Group" onclick="removeRemoteGroupRow(${gIdx})">✕</button>
          </div>
        </div>
        <div>
          <small style="color:var(--muted);display:block;margin-bottom:5px;font-size:11px;">Remotes in Group (Click to Enable/Disable; First Selected = Primary Power Target)</small>
          <div class="dock-pill-list">${pillsHtml}</div>
        </div>
      </div>`;
    }).join("");
  }
  renderDeviceRemoteAssignments();
}

function addRemoteGroupRow() {
  const idx = REMOTE_GROUPS_STATE.length + 1;
  REMOTE_GROUPS_STATE.push({
    id: `rg_${Date.now()}_${idx}`,
    name: `Area Group ${idx}`,
    area_id: "",
    remotes: []
  });
  renderRemoteGroupsEditor();
}

function removeRemoteGroupRow(gIdx) {
  REMOTE_GROUPS_STATE.splice(gIdx, 1);
  markDirty();
  renderRemoteGroupsEditor();
}

function updateRemoteGroupField(gIdx, field, val) {
  if (!REMOTE_GROUPS_STATE[gIdx]) return;
  REMOTE_GROUPS_STATE[gIdx][field] = val;
  markDirty();
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
  markDirty();
  renderRemoteGroupsEditor();
}

function renderDeviceRemoteAssignments() {
  const box = doc.getElementById("device-remote-assignments-list");
  if (!box) return;
  const devs = (STATE?.system_devices || []).filter(d => d.device_profile !== "ble_beacon" && d.device_profile !== "headless_node");
  if (!devs.length) {
    box.innerHTML = `<p style="color:var(--muted);font-size:12.5px;margin:0;">No display devices onboarded.</p>`;
    return;
  }
  box.innerHTML = devs.map(d => {
    const curMode = d.device_remote_group || "area_auto";
    const opts = [
      `<option value="area_auto" ${curMode === 'area_auto' ? 'selected' : ''}>Follow Active Area (Hide Remote App When Area Has None)</option>`,
      ...REMOTE_GROUPS_STATE.map(g =>
        `<option value="${esc('group:' + g.id)}" ${curMode === ('group:' + g.id) ? 'selected' : ''}>Static Group: ${esc(g.name)}</option>`
      ),
      `<option value="all" ${curMode === 'all' ? 'selected' : ''}>All System Remotes</option>`
    ].join("");
    return `<div class="native-ctrl-row">
      <div class="lbl">
        ${esc(d.title)}
        <small>Active Area: ${esc(d.active_area_name || 'Unassigned')}</small>
      </div>
      <div class="widget">
        <select onchange="assignDeviceRemoteGroup(${jsArg(d.subentry_id)}, ${jsArg(d.title)}, this.value)">${opts}</select>
      </div>
    </div>`;
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
    showToast("Maximum of 10 remote controls reached");
    return;
  }
  const row = document.createElement("div");
  row.className = "native-ctrl-row remote-row-item";
  row.style.marginBottom = "8px";
  const remOptions = (STATE?.catalog?.remotes || []).map(r =>
    `<option value="${esc(r.id)}" ${r.id === entityId ? 'selected' : ''}>${esc(r.name)}</option>`
  ).join("");
  const slotTitle = existingCount === 0
    ? "Slot 1 (Primary Power Target)"
    : `Slot ${existingCount + 1}`;
  row.innerHTML = `
    <div style="flex:1;min-width:0;">
      <small class="rem-slot-lbl" style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;font-weight:500;">${esc(slotTitle)}</small>
      <select class="rem-ent-sel" style="width:100%;max-width:none;" onchange="markDirty(); renderRemoteGroupsEditor();"><option value="">— Select Remote or Media Player —</option>${remOptions}</select>
    </div>
    <button type="button" class="btn-danger" title="Remove Remote" onclick="this.parentElement.remove(); renumberRemoteControlRows(); markDirty();">✕</button>
  `;
  list.appendChild(row);
}

function addVolumeOverrideRow(speaker="", target="") {
  const list = doc.getElementById("volume-overrides-list");
  if (!list) return;
  const existingCount = list.querySelectorAll(".vol-override-row").length;
  if (existingCount >= 10) {
    showToast("Maximum of 10 volume overrides reached");
    return;
  }
  const row = document.createElement("div");
  row.className = "native-ctrl-row vol-override-row";
  row.style.marginBottom = "8px";
  const spkOptions = (STATE?.catalog?.ma_speakers || []).map(s =>
    `<option value="${esc(s.id)}" ${s.id === speaker ? 'selected' : ''}>${esc(s.name)}</option>`
  ).join("");
  const tgtOptions = (STATE?.catalog?.volume_targets || []).map(t =>
    `<option value="${esc(t.id)}" ${t.id === target ? 'selected' : ''}>${esc(t.name)}</option>`
  ).join("");
  row.innerHTML = `
    <div class="form-grid-2" style="flex:1;min-width:0;">
      <div>
        <small style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;">When Streaming To Speaker</small>
        <select class="vo-spk" style="width:100%;max-width:none;" onchange="markDirty()"><option value="">— Select Speaker —</option>${spkOptions}</select>
      </div>
      <div>
        <small style="color:var(--muted);display:block;margin-bottom:3px;font-size:11px;">Control Volume On</small>
        <select class="vo-tgt" style="width:100%;max-width:none;" onchange="markDirty()"><option value="">— Select Volume Target —</option>${tgtOptions}</select>
      </div>
    </div>
    <button type="button" class="btn-danger" title="Remove Override" onclick="this.parentElement.remove(); markDirty();">✕</button>
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
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    doc.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    doc.body.removeChild(ta);
    showToast(ok ? successMsg : "Copy failed — select text manually");
  } catch (_e) {
    showToast("Copy failed — select text manually");
  }
}


function copyTextById(elId) {
  const text = doc.getElementById(elId)?.textContent || "";
  copyToClipboard(text, "Copied to clipboard");
}

let pendingRemoveEntryId = "";
let pendingRemoveTitle = "";

function ensureRemoveDeviceModal() {
  if (doc.getElementById("latter-rm-modal")) return;
  const modal = document.createElement("div");
  modal.id = "latter-rm-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(8,12,18,0.82);backdrop-filter:blur(6px);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px;";
  modal.innerHTML = `
    <div class="card" style="max-width:400px;width:100%;margin:0;">
      <h3 style="margin-bottom:6px;color:var(--danger);">Remove Device from Latter?</h3>
      <p class="desc" id="latter-rm-desc" style="margin-bottom:16px;">Remove this device from Latter? Your ESPHome device will remain in Home Assistant.</p>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button type="button" class="btn-secondary" onclick="closeRemoveDeviceModal()">Cancel</button>
        <button type="button" class="btn-danger" id="latter-rm-confirm-btn" onclick="confirmRemoveManagedDevice()">Remove Device</button>
      </div>
    </div>
  `;
  doc.body.appendChild(modal);
}

function closeRemoveDeviceModal() {
  const m = doc.getElementById("latter-rm-modal");
  if (m) m.style.display = "none";
  pendingRemoveEntryId = "";
  pendingRemoveTitle = "";
}

function removeManagedDevice(entryId, title) {
  ensureRemoveDeviceModal();
  pendingRemoveEntryId = entryId;
  pendingRemoveTitle = title || entryId;
  const desc = doc.getElementById("latter-rm-desc");
  if (desc) {
    desc.textContent = `Remove '${pendingRemoveTitle}' from Latter? Your ESPHome device will remain in Home Assistant, and you can re-add it anytime.`;
  }
  doc.getElementById("latter-rm-modal").style.display = "flex";
}

async function confirmRemoveManagedDevice() {
  const entryId = pendingRemoveEntryId;
  const title = pendingRemoveTitle;
  closeRemoveDeviceModal();
  if (!entryId) return;
  const data = await callStudioCommand({command: "remove_device", subentry_id: entryId});
  if (data) {
    const data = data;
    if (data.removed) {
      ACTIVE_SUBENTRY_ID = data.next_subentry_id || "";
      DEVICE_SELECTED = false;
      setScope("device", "select_device_prompt");
    }
    applyStateToDom(data, false);
    showToast(`Removed '${title}' from Latter`);
  } else {
    showToast("Failed to remove device");
  }
}

function ensureAddDeviceModal() {
  if (doc.getElementById("latter-add-dev-modal")) return;
  const modal = document.createElement("div");
  modal.id = "latter-add-dev-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(8,12,18,0.82);backdrop-filter:blur(6px);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px;";
  modal.innerHTML = `
    <div class="card" style="max-width:460px;width:100%;margin:0;">
      <h3 style="margin-bottom:12px;">Add BLE Phone, Watch or Tag</h3>
      <p style="color:var(--muted);font-size:13px;margin:0 0 12px;">Latter devices are added through Home Assistant's ESPHome discovery.</p>

      <div id="add-dev-pane-ble">
        <div class="field">
          <label>Discovered Bluetooth / Private BLE / iBeacon Devices</label>
          <select id="ble-candidate-picker" onchange="onSelectBleCandidate(this.value)"></select>
        </div>
        <div class="field">
          <label>Device Name</label>
          <input type="text" id="ble-custom-name" placeholder="e.g. Phone, Watch, Keys">
        </div>
        <div class="field">
          <label>BLE MAC Address, Entity ID (private_ble_device), or iBeacon UUID</label>
          <input type="text" id="ble-custom-addr" class="mono" placeholder="AA:BB:CC:DD:EE:FF or device_tracker.iphone_ble">
        </div>
        <div class="field">
          <label>Assign to Person (Optional — Creates <code>sensor.&lt;person&gt;_current_area</code>)</label>
          <select id="ble-custom-person"></select>
        </div>
      </div>

      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
        <button type="button" class="btn-secondary" onclick="closeAddDeviceModal()">Cancel</button>
        <button type="button" class="btn-primary" id="btn-confirm-add-device" onclick="confirmAddDeviceModal()">Add Device</button>
      </div>
    </div>
  `;
  doc.body.appendChild(modal);
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
  ensureAddDeviceModal();
  const bleCands = STATE?.discovered_ble_devices || [];

  const blePicker = doc.getElementById("ble-candidate-picker");
  if (blePicker) {
    const opts = [`<option value="">— Select Discovered BLE Device or Enter Below —</option>`].concat(
      bleCands.map(c => `<option value="${esc(c.target_address)}">${esc(c.label)}</option>`)
    );
    blePicker.innerHTML = opts.join("");
  }
  const nameInp = doc.getElementById("ble-custom-name");
  const addrInp = doc.getElementById("ble-custom-addr");
  if (nameInp) nameInp.value = "";
  if (addrInp) addrInp.value = "";
  populateSelect("ble-custom-person", STATE?.catalog?.persons || [], "", true);

  doc.getElementById("latter-add-dev-modal").style.display = "flex";
}

function closeAddDeviceModal() {
  const m = doc.getElementById("latter-add-dev-modal");
  if (m) m.style.display = "none";
}

async function confirmAddDeviceModal() {
  const name = doc.getElementById("ble-custom-name")?.value?.trim() || "";
  const target_address = doc.getElementById("ble-custom-addr")?.value?.trim() || "";
  const assigned_person = doc.getElementById("ble-custom-person")?.value || "";
  if (!name || !target_address) {
    showToast("Enter a Device Name and BLE Address/Entity");
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
  markDirty();
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

async function captureCurrentDeviceProfile() {
  const nameEl = doc.getElementById("new-profile-name");
  const descEl = doc.getElementById("new-profile-desc");
  const name = (nameEl?.value || "").trim() || `${STATE?.title || 'Device'} Profile`;
  const data = await callStudioCommand({command: "capture_profile", name, description: (descEl?.value || "").trim()});
  if (data) {
    if (nameEl) nameEl.value = "";
    if (descEl) descEl.value = "";
    applyStateToDom(data, false);
    showToast(`Saved profile '${name}'`);
  }
}

async function applySavedProfile(profileId) {
  const scope = doc.getElementById("profile-target-scope")?.value || "current";
  const data = await callStudioCommand({command: "apply_profile", profile_id: profileId, target_scope: scope});
  if (data) {
    applyStateToDom(data, true);
    showToast(`Applied profile to ${scope}`);
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
  if (!HASS_REF) return;
  const scope = overrideScope || doc.getElementById("bkp-scope-select")?.value || "system";
  const wsType = scope === "device" ? "latter/device/export" : "latter/system/export";
  const data = await HASS_REF.callWS({
    type: wsType,
    subentry_id: ACTIVE_SUBENTRY_ID || null,
    scope
  });
  if (data && data.bundle) {
    triggerJsonDownload(data.bundle);
    showToast(`Downloaded ${scope} backup .JSON`);
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
    try {
      const parsed = JSON.parse(reader.result);
      const bundle = parsed.bundle || parsed;
      const wsType = bundle.scope === "device" ? "latter/device/import" : "latter/system/import";
      const data = await HASS_REF.callWS({
        type: wsType,
        subentry_id: ACTIVE_SUBENTRY_ID || null,
        bundle,
        restore_esphome_entities: restoreEsp
      });
      if (data) {
        input.value = "";
        applyStateToDom(data, true);
        showToast(`Restored ${bundle.scope || "backup"} from file`);
      }
    } catch (_e) {
      showToast("Restore failed: invalid JSON backup file");
    }
  };
  reader.readAsText(file);
}

function applyStateToDom(data, forceFormUpdate=false) {
  STATE = data;
  const cfg = data.config;
  const live = data.live;
  const cat = data.catalog;
  const esp = data.esphome;

  const areaName = live.active_area_name || "Home";
  const caps = data.capabilities || {};
  const devTitle = esp?.device?.name || data.title;
  updateTopHeaderForScope();

  // Capability-Aware Device Sidebar Tabs
  const showDisplay = !!caps.has_display;
  const showPower = !!caps.has_power;
  const showAudioVoice = !!(caps.has_voice || caps.has_audio);
  doc.getElementById("nav-btn-home_display")?.classList.toggle("hidden", !showDisplay);
  doc.getElementById("nav-btn-audio_voice")?.classList.toggle("hidden", !showAudioVoice);
  doc.getElementById("nav-btn-power")?.classList.toggle("hidden", !showPower);

  // Extract live Battery, Wi-Fi/BLE & IP/Target from current device's system entry
  const curDevEntry = (data.system_devices || []).find(d => d.is_current) || {};
  const isBleOnly = cfg.device_profile === "ble_beacon";
  const isStationary = cfg.device_profile === "stationary_display";
  const winBleRow = (live.ble_survey_rows || []).find(r => r.is_winner);
  let batText = "Plugged In";
  if (isBleOnly) {
    batText = "BLE Beacon";
  } else if (curDevEntry.battery_level !== null && curDevEntry.battery_level !== undefined && !isStationary) {
    if (curDevEntry.is_charging) {
      batText = `${curDevEntry.battery_level}% (Charging)`;
    } else if (curDevEntry.is_usb_connected) {
      batText = `${curDevEntry.battery_level}% (Plugged In)`;
    } else {
      batText = `${curDevEntry.battery_level}%`;
    }
  }
  const wifiText = (curDevEntry.wifi_rssi !== null && curDevEntry.wifi_rssi !== undefined)
    ? `${curDevEntry.wifi_rssi} dBm`
    : (isBleOnly && winBleRow && winBleRow.effective_rssi !== null ? `${winBleRow.effective_rssi} dBm (BLE)` : (curDevEntry.status_label || "Online"));
  const ipStr = curDevEntry.ip_address || (isBleOnly ? (cfg.ble_target_address || "BLE Tracked") : "Connected");

  const hasAssignedArea = !!curDevEntry.has_assigned_area;
  const isRoaming = !hasAssignedArea;
  const areaLblEl = doc.getElementById("st-area-label");
  if (areaLblEl) areaLblEl.textContent = hasAssignedArea ? "Area" : "Current Area (Roaming)";

  // 4 Hero Stat Boxes on Device Overview
  const rawDevSw = String(live.device_sw_version || esp?.device?.sw_version || data.version || "2.2.0").replace(/^v/i, "");
  doc.getElementById("dash-header-title").textContent = "Overview";
  doc.getElementById("st-area").textContent = hasAssignedArea ? (curDevEntry.area_label || areaName) : areaName;
  doc.getElementById("st-battery").textContent = batText;
  doc.getElementById("st-wifi").textContent = wifiText;
  const fwEl = doc.getElementById("st-fw-version");
  if (fwEl) {
    fwEl.textContent = live.fw_update_available ? `v${rawDevSw} (Update)` : `v${rawDevSw}`;
  }

  const grpList = data.device_groups || [];
  const grpObj = grpList.find(g => g.id === cfg.device_group);
  doc.getElementById("st-group").textContent = grpObj ? grpObj.name : (cfg.device_group || "Unassigned");

  const hwModel = curDevEntry.model_label || esp?.device?.model || "ESPHome Node";
  doc.getElementById("dash-hw-model").textContent = hwModel;
  doc.getElementById("dash-ip-addr").textContent = ipStr;
  doc.getElementById("dash-ble-mode").textContent = isRoaming
    ? `Roaming (BLE Auto-Switch • ${areaName})`
    : `Stationary (${areaName})`;
  const winRow = (live.ble_survey_rows || []).find(r => r.is_winner);
  const distSuffix = (winRow && winRow.distance_m != null) ? ` (~${winRow.distance_m}m / ${winRow.distance_ft}ft)` : "";
  doc.getElementById("dash-ble-proxy").textContent = (live.ble_closest_proxy || "None") + distSuffix;
  const proxyRow = doc.getElementById("dash-row-ble-proxy");
  if (proxyRow) proxyRow.style.display = (caps.has_ble_beacon && cfg.native_ble_tracking) ? "flex" : "none";

  renderLogsView();
  renderActiveSurveyDeviceBars();
  renderWallpaperGallery(data.wallpapers, cfg.device_slug, cfg.display_shape);
  const activeEl = getStudioActiveElement();
  if (!activeEl || !["SELECT", "INPUT"].includes(activeEl.tagName)) {
    renderCohesiveDeviceSections();
    renderSystemOverview(data.system_devices, data.system_controls, cfg);
  }

  if (!INITIAL_FORM_LOADED || forceFormUpdate) {
    INITIAL_FORM_LOADED = true;
            renderCohesiveDeviceSections();
    renderSystemOverview(data.system_devices, data.system_controls, cfg);

    doc.getElementById("cfg-device_slug").value = cfg.device_slug || "";
    doc.getElementById("cfg-companion_base_url").value = cfg.companion_base_url || "";
    doc.getElementById("cfg-device_profile").value = cfg.device_profile || "mobile_display";
    doc.getElementById("cfg-display_shape").value = cfg.display_shape || "circle";
    doc.getElementById("cfg-default_page_size").value = cfg.default_page_size ?? 3;
    doc.getElementById("cfg-native_ble_tracking").checked = !!cfg.native_ble_tracking;
    doc.getElementById("cfg-ble_auto_switch").checked = !!cfg.ble_auto_switch;
    doc.getElementById("cfg-sync_device_area").checked = !!cfg.sync_device_area;
    const syncAreaRow = doc.getElementById("row-sync-device-area");
    if (syncAreaRow) {
      syncAreaRow.classList.toggle("hidden", STATE?.capabilities?.is_roaming_device === false);
    }
    doc.getElementById("cfg-area_handoff").checked = !!cfg.area_handoff;
    doc.getElementById("cfg-ble_beacon_uuid").value = cfg.ble_beacon_uuid || "";
    if (doc.getElementById("cfg-ble_target_address")) {
      doc.getElementById("cfg-ble_target_address").value = cfg.ble_target_address || "";
    }
    doc.getElementById("cfg-dock_apps").value = cfg.dock_apps || "music,alarm,area,remote,games,tools";
    renderDockPillsFromInput();
    doc.getElementById("cfg-wallpaper_source").value = cfg.wallpaper_source || "";
    doc.getElementById("cfg-wallpaper_cycle_minutes").value = String(cfg.wallpaper_cycle_minutes || 0);
    doc.getElementById("cfg-art_size").value = String(cfg.art_size || 466);
    if (doc.getElementById("cfg-doorbell_noise_reduction")) {
      doc.getElementById("cfg-doorbell_noise_reduction").value = cfg.doorbell_noise_reduction || "strong";
    }

    populateSelect("cfg-default_area", cat.areas, cfg.default_area);
    populateSelect("cfg-presence_entity", cat.presence_sensors, cfg.presence_entity);
    populateSelect("cfg-assigned_person", cat.persons, cfg.assigned_person);
    populateSelect("cfg-default_speaker", cat.ma_speakers, cfg.default_speaker, true);
    const voListEl = doc.getElementById("volume-overrides-list");
    if (voListEl) {
      voListEl.innerHTML = "";
      let voItems = Array.isArray(cfg.volume_overrides) ? cfg.volume_overrides : [];
      if (!voItems.length) {
        if (cfg.vol_speaker_1 && cfg.vol_target_1) voItems.push({speaker: cfg.vol_speaker_1, target: cfg.vol_target_1});
        if (cfg.vol_speaker_2 && cfg.vol_target_2) voItems.push({speaker: cfg.vol_speaker_2, target: cfg.vol_target_2});
      }
      voItems.forEach(vo => {
        if (vo && vo.speaker && vo.target) addVolumeOverrideRow(vo.speaker, vo.target);
      });
    }
    const remListEl = doc.getElementById("remotes-list");
    if (remListEl) {
      remListEl.innerHTML = "";
      let remItems = Array.isArray(cfg.remotes_list) ? cfg.remotes_list.filter(Boolean) : [];
      if (!remItems.length) {
        [cfg.remote_1, cfg.remote_2, cfg.remote_3, cfg.remote_4].forEach(r => {
          if (r) remItems.push(r);
        });
      }
      remItems.forEach(rId => addRemoteControlRow(rId));
    }
    REMOTE_GROUPS_STATE = Array.isArray(cfg.remote_groups) ? JSON.parse(JSON.stringify(cfg.remote_groups)) : [];
    renderRemoteGroupsEditor();
    populateSelect("cfg-alarm_entity", cat.alarms, cfg.alarm_entity);
    populateSelect("cfg-weather_entity", cat.weathers, cfg.weather_entity);
    populateSelect("cfg-thermostat_entity", cat.climates, cfg.thermostat_entity);
    populateSelect("cfg-lock_entity", cat.locks, cfg.lock_entity);
    populateSelect("cfg-garage_entity", cat.garages, cfg.garage_entity);
    populateSelect("cfg-vacuum_entity", cat.vacuums, cfg.vacuum_entity);

    const camListEl = doc.getElementById("cameras-list");
    if (camListEl) {
      camListEl.innerHTML = "";
      let camItems = Array.isArray(cfg.camera_entities) ? cfg.camera_entities.filter(Boolean) : [];
      if (!camItems.length && cfg.camera_entity) {
        camItems.push(cfg.camera_entity);
      }
      camItems.forEach(cId => addCameraRow(cId));
    }

    const calListEl = doc.getElementById("calendars-list");
    if (calListEl) {
      calListEl.innerHTML = "";
      const calItems = Array.isArray(cfg.calendar_entities) ? cfg.calendar_entities.filter(Boolean) : [];
      calItems.forEach(cId => addCalendarRow(cId));
    }

    clearDirty();
  }
  renderCustomColorPalettes();
}

async function refreshState(forceForm=false) {
  if (!HASS_REF) return;
  try {
    const data = await HASS_REF.callWS({
      type: "latter/system/get_state",
      subentry_id: ACTIVE_SUBENTRY_ID || null,
      studio_rev: 2
    });
    if (data) {
      if (!ACTIVE_SUBENTRY_ID && data.subentry_id) {
        ACTIVE_SUBENTRY_ID = data.subentry_id;
      }
      applyStateToDom(data, forceForm);
    }
  } catch (err) {
    console.warn("Latter Studio get_state error:", err);
  }
}

async function saveAllConfig() {
  const volumeOverrides = [];
  doc.querySelectorAll("#volume-overrides-list .vol-override-row").forEach(row => {
    const speaker = row.querySelector(".vo-spk")?.value?.trim() || "";
    const target = row.querySelector(".vo-tgt")?.value?.trim() || "";
    if (speaker && target) volumeOverrides.push({speaker, target});
  });

  const remotesList = [];
  doc.querySelectorAll("#remotes-list .remote-row-item").forEach(row => {
    const rEnt = row.querySelector(".rem-ent-sel")?.value?.trim() || "";
    if (rEnt) remotesList.push(rEnt);
  });

  const cameraEntities = [];
  doc.querySelectorAll("#cameras-list .camera-row-item").forEach(row => {
    const cEnt = row.querySelector(".cam-ent-sel")?.value?.trim() || "";
    if (cEnt && !cameraEntities.includes(cEnt)) cameraEntities.push(cEnt);
  });

  const calendarEntities = [];
  doc.querySelectorAll("#calendars-list .calendar-row-item").forEach(row => {
    const calEnt = row.querySelector(".cal-ent-sel")?.value?.trim() || "";
    if (calEnt && !calendarEntities.includes(calEnt)) calendarEntities.push(calEnt);
  });

  const artVal = String(doc.getElementById("cfg-art_size")?.value || "466");
  const config = {
    companion_base_url: doc.getElementById("cfg-companion_base_url")?.value?.trim() || "",
    device_profile: doc.getElementById("cfg-device_profile")?.value || (STATE?.config?.device_profile || "mobile_display"),
    device_group: doc.getElementById("cfg-device_group")?.value || "handhelds",
    display_shape: doc.getElementById("cfg-display_shape")?.value || (STATE?.config?.display_shape || "round"),
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
    volume_overrides: volumeOverrides,
    vol_speaker_1: volumeOverrides[0]?.speaker || "",
    vol_target_1: volumeOverrides[0]?.target || "",
    vol_speaker_2: volumeOverrides[1]?.speaker || "",
    vol_target_2: volumeOverrides[1]?.target || "",
    remotes_list: remotesList,
    remote_groups: REMOTE_GROUPS_STATE,
    remote_1: remotesList[0] || "",
    remote_2: remotesList[1] || "",
    remote_3: remotesList[2] || "",
    remote_4: remotesList[3] || "",
    alarm_entity: doc.getElementById("cfg-alarm_entity")?.value ?? "",
    camera_entity: cameraEntities[0] || "",
    camera_entities: cameraEntities,
    weather_entity: doc.getElementById("cfg-weather_entity")?.value ?? "",
    thermostat_entity: doc.getElementById("cfg-thermostat_entity")?.value ?? "",
    lock_entity: doc.getElementById("cfg-lock_entity")?.value ?? "",
    garage_entity: doc.getElementById("cfg-garage_entity")?.value ?? "",
    vacuum_entity: doc.getElementById("cfg-vacuum_entity")?.value ?? "",
    default_area: doc.getElementById("cfg-default_area")?.value ?? "",
    dock_apps: doc.getElementById("cfg-dock_apps")?.value?.trim() || "",
    wallpaper_source: doc.getElementById("cfg-wallpaper_source")?.value?.trim() || "",
    wallpaper_cycle_minutes: parseInt(doc.getElementById("cfg-wallpaper_cycle_minutes")?.value || "0", 10) || 0,
    art_size: artVal.includes("x") ? artVal : (parseInt(artVal, 10) || 466),
    calendar_entities: calendarEntities,
    custom_palettes: Array.isArray((STATE?.config || {}).custom_palettes) ? STATE.config.custom_palettes : [],
    device_custom_color: (STATE?.config || {}).device_custom_color || "#3898FF",
    doorbell_noise_reduction: doc.getElementById("cfg-doorbell_noise_reduction")?.value || "strong",
  };

  const btn = doc.getElementById("btn-save-changes");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }
  try {
    const data = await callStudioCommand({command: "save_config", config});
    if (data) {
      applyStateToDom(data, true);
      showToast("Saved configuration");
    } else if (btn) {
      btn.disabled = false;
      btn.textContent = "Save Changes";
    }
  } catch (err) {
    console.error("Latter Studio save_config failed:", err);
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Save Changes";
    }
    showToast(`Save failed: ${err?.message || err || "Unknown error"}`);
  }
}

let cwTargetScope = "device";
let cwSelectedHex = "#3898FF";

function ensureColorWheelModal() {
  if (doc.getElementById("latter-cw-modal")) return;
  const modal = document.createElement("div");
  modal.id = "latter-cw-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(8,12,18,0.82);backdrop-filter:blur(6px);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px;";
  modal.innerHTML = `
    <div class="card" style="max-width:380px;width:100%;margin:0;text-align:center;position:relative;">
      <h3 style="margin-bottom:4px;">HSV Color Wheel Picker</h3>
      <p class="desc" style="margin-bottom:12px;">Select a custom UI accent color and save it to your system color library.</p>
      <div style="display:flex;justify-content:center;margin-bottom:14px;">
        <canvas id="latter-cw-canvas" width="220" height="220" style="border-radius:50%;cursor:crosshair;box-shadow:0 4px 20px rgba(0,0,0,0.45);"></canvas>
      </div>
      <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:12px;">
        <span id="latter-cw-preview" style="width:32px;height:32px;border-radius:50%;border:2px solid #fff;background:#3898FF;"></span>
        <input type="text" id="latter-cw-hex" value="#3898FF" style="width:110px;font-family:monospace;text-align:center;" oninput="onCwHexInput(this.value)">
      </div>
      <div class="field" style="text-align:left;margin-bottom:14px;">
        <label>Color Profile Name</label>
        <input type="text" id="latter-cw-name" placeholder="e.g. Sunset Coral">
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button type="button" class="btn-secondary" onclick="closeColorWheelModal()">Cancel</button>
        <button type="button" class="btn-primary" onclick="saveColorWheelSelection()">Save Color</button>
      </div>
    </div>
  `;
  doc.body.appendChild(modal);

  const canvas = doc.getElementById("latter-cw-canvas");
  const ctx = canvas.getContext("2d");
  const cx = 110, cy = 110, r = 108;
  const img = ctx.createImageData(220, 220);
  for (let y = 0; y < 220; y++) {
    for (let x = 0; x < 220; x++) {
      const dx = x - cx, dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * 220 + x) * 4;
      if (dist <= r) {
        let hue = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
        let sat = Math.min(1, dist / r);
        const [cr, cg, cb] = hsvToRgbJS(hue, sat, 1.0);
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
    const sat = dist / r;
    const [cr, cg, cb] = hsvToRgbJS(hue, sat, 1.0);
    const hex = "#" + [cr, cg, cb].map(v => v.toString(16).padStart(2, "0")).join("").toUpperCase();
    setCwHex(hex);
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
  cwSelectedHex = hex.toUpperCase();
  const prev = doc.getElementById("latter-cw-preview");
  const inp = doc.getElementById("latter-cw-hex");
  if (prev) prev.style.background = cwSelectedHex;
  if (inp && getStudioActiveElement() !== inp) inp.value = cwSelectedHex;
}

function onCwHexInput(val) {
  let v = val.trim().toUpperCase();
  if (!v.startsWith("#")) v = "#" + v;
  if (/^#[0-9A-F]{6}$/.test(v)) {
    cwSelectedHex = v;
    const prev = doc.getElementById("latter-cw-preview");
    if (prev) prev.style.background = v;
  }
}

function openColorWheelModal(scope) {
  ensureColorWheelModal();
  cwTargetScope = scope || "device";
  const curHex = ((STATE && STATE.config && STATE.config.device_custom_color) || "#3898FF").toUpperCase();
  setCwHex(curHex);
  const nameInp = doc.getElementById("latter-cw-name");
  if (nameInp) nameInp.value = "";
  doc.getElementById("latter-cw-modal").style.display = "flex";
}

function closeColorWheelModal() {
  const m = doc.getElementById("latter-cw-modal");
  if (m) m.style.display = "none";
}

async function saveColorWheelSelection() {
  const nameInp = doc.getElementById("latter-cw-name");
  const name = (nameInp && nameInp.value.trim()) ? nameInp.value.trim() : `Custom (${cwSelectedHex})`;
  STATE.config = STATE.config || {};
  let pals = Array.isArray(STATE.config.custom_palettes) ? [...STATE.config.custom_palettes] : [];
  const existing = pals.find(p => (p.hex || "").toUpperCase() === cwSelectedHex);
  if (existing) {
    existing.name = name;
  } else {
    pals.unshift({name, hex: cwSelectedHex});
  }
  STATE.config.custom_palettes = pals;
  STATE.config.device_custom_color = cwSelectedHex;
  closeColorWheelModal();
  await applyDeviceCustomColor(cwSelectedHex, true);
}

async function applyDeviceCustomColor(hexColor, alsoSwitchSelect) {
  STATE.config = STATE.config || {};
  STATE.config.device_custom_color = hexColor.toUpperCase();
  await saveAllConfig();
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
  STATE.config = STATE.config || {};
  let pals = Array.isArray(STATE.config.custom_palettes) ? STATE.config.custom_palettes : [];
  STATE.config.custom_palettes = pals.filter(p => (p.hex || "").toUpperCase() !== hexColor.toUpperCase());
  await saveAllConfig();
}

function renderCustomColorPalettes() {
  if (!STATE || !STATE.config) return;
  const pals = Array.isArray(STATE.config.custom_palettes) ? STATE.config.custom_palettes : [];
  const curHex = (STATE.config.device_custom_color || "#3898FF").toUpperCase();

  const sw = doc.getElementById("dev-color-swatch");
  if (sw) sw.style.background = curHex;

  const sel = doc.getElementById("dev-custom-palette-select");
  if (sel) {
    let optsHtml = "";
    if (pals.length === 0) {
      optsHtml += `<option value="${esc(curHex)}">Active Custom (${esc(curHex)})</option>`;
    } else {
      for (const p of pals) {
        const h = (p.hex || "").toUpperCase();
        const selAttr = (h === curHex) ? "selected" : "";
        optsHtml += `<option value="${esc(h)}" ${selAttr}>${esc(p.name || h)} (${esc(h)})</option>`;
      }
    }
    optsHtml += `<option value="__new__">+ Create New Color (Wheel)...</option>`;
    sel.innerHTML = optsHtml;
  }

  const sysBox = doc.getElementById("sys-custom-palettes-list");
  if (sysBox) {
    if (pals.length === 0) {
      sysBox.innerHTML = `<p class="desc" style="margin:0;">No custom colors saved yet. Click "+ Open Color Wheel" to create one.</p>`;
    } else {
      sysBox.innerHTML = pals.map(p => {
        const h = (p.hex || "").toUpperCase();
        return `
          <div style="display:inline-flex;align-items:center;gap:8px;padding:5px 11px;border-radius:18px;background:var(--input-bg);border:1px solid var(--border);">
            <span style="width:14px;height:14px;border-radius:50%;background:${esc(h)};border:1px solid #fff;"></span>
            <strong style="font-size:12.5px;font-weight:500;">${esc(p.name || h)}</strong>
            <code style="font-size:11px;opacity:0.75;">${esc(h)}</code>
            <button type="button" class="btn-secondary" style="padding:2px 8px;font-size:11px;" onclick="applyDeviceCustomColor(${jsArg(h)}, true)">Apply</button>
            <button type="button" class="btn-secondary" style="padding:2px 6px;font-size:11px;color:var(--danger);" onclick="deleteCustomPalette(${jsArg(h)})">&times;</button>
          </div>
        `;
      }).join("");
    }
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
  window.captureCurrentDeviceProfile = captureCurrentDeviceProfile;
  window.checkSystemUpdates = checkSystemUpdates;
  window.clearDirty = clearDirty;
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
  window.ensureAddDeviceModal = ensureAddDeviceModal;
  window.ensureColorWheelModal = ensureColorWheelModal;
  window.ensureRemoveDeviceModal = ensureRemoveDeviceModal;
  window.espAction = espAction;
  window.espNumber = espNumber;
  window.espSelect = espSelect;
  window.exportBackupToComputer = exportBackupToComputer;
  window.fallbackCopyText = fallbackCopyText;
    window.getInventoryRemoteIds = getInventoryRemoteIds;
  window.getRemoteFriendlyLabel = getRemoteFriendlyLabel;
  window.getSectionItems = getSectionItems;
  window.hsvToRgbJS = hsvToRgbJS;
  window.markDirty = markDirty;
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
  window.openSystemSection = openSystemSection;
  window.populateSelect = populateSelect;
  window.quickAdoptBleCandidate = quickAdoptBleCandidate;
  window.refreshActiveCameraPreview = refreshActiveCameraPreview;
  window.refreshState = refreshState;
  window.removeManagedDevice = removeManagedDevice;
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
  window.saveAllConfig = saveAllConfig;
  window.saveColorWheelSelection = saveColorWheelSelection;
  window.selectCurrentDevice = selectCurrentDevice;
  window.selectWallpaperSource = selectWallpaperSource;
  window.sendTestNotification = sendTestNotification;
  window.setAreaFusionMode = setAreaFusionMode;
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
    const path = String((this._route && this._route.path) || window.location.pathname || "");
    const devMatch = path.match(/\/devices\/([^/?#]+)/);
    const params = new URLSearchParams(window.location.search);
    const querySub = params.get("subentry_id") || params.get("device") || "";
    if (devMatch && devMatch[1]) {
      ACTIVE_SUBENTRY_ID = decodeURIComponent(devMatch[1]);
      DEVICE_SELECTED = true;
      setScope("device", "dashboard");
      if (this._hass) {
        this._resubscribe(true);
      }
    } else if (querySub) {
      ACTIVE_SUBENTRY_ID = querySub;
      DEVICE_SELECTED = true;
      setScope("device", "dashboard");
      if (this._hass) {
        this._resubscribe(true);
      }
    } else if (!DEVICE_SELECTED) {
      setScope("system", "system_overview");
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
          if (myGen !== SUB_GEN || !eventPayload || IS_DIRTY) return;
          if (
            ACTIVE_SUBENTRY_ID &&
            eventPayload.subentry_id &&
            eventPayload.subentry_id !== ACTIVE_SUBENTRY_ID
          ) {
            return;
          }
          applyStateToDom(eventPayload, false);
        },
        {
          type: "latter/system/subscribe",
          subentry_id: targetSubId,
          studio_rev: 2
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
      toggleSurveyFastMode(false);
    }
  }
}

if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
