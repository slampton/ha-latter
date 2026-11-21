/**
 * Title bar, two-pane RTL-safe sidebar shell, navigation badges, & two-column layout (`D-014`).
 */

import { css } from "../lib/lit.js";

export const LAYOUT_STYLES = css`
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-block-end: var(--studio-header-border);
    position: sticky;
    inset-block-start: 0;
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
  :host([show-menu]) .titlebar-brand .ha-menu-btn { display: inline-flex; }
  .titlebar-title { padding-inline-start: var(--studio-space-3); }
  :host([show-menu]) .titlebar-title { padding-inline-start: 0; }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }

  .app-shell {
    display: grid;
    grid-template-columns: var(--studio-sidebar-width) minmax(0, 1fr);
    min-height: calc(100vh - var(--studio-header-height));
    min-height: calc(100dvh - var(--studio-header-height));
  }
  aside.sidebar {
    background: var(--studio-sidebar-bg);
    border-inline-end: 1px solid var(--studio-divider);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-4);
    padding-inline: var(--studio-space-3);
    position: sticky;
    inset-block-start: var(--studio-header-height);
    height: calc(100vh - var(--studio-header-height));
    height: calc(100dvh - var(--studio-header-height));
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
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-align: start;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
  }
  .nav-btn:hover { background: var(--studio-hover); }
  .nav-btn.active {
    background: var(--studio-nav-active-bg);
    color: var(--studio-nav-active-text);
  }
  .nav-btn.nav-back-btn { color: var(--studio-text-secondary); }
  .nav-device-title {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border-block-start: 1px solid var(--studio-divider);
    border-block-end: 1px solid var(--studio-divider);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-inline-start: var(--studio-space-4); }
  .nav-badge {
    min-inline-size: 20px;
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .main-area { min-inline-size: 0; }
  .content-wrap {
    max-inline-size: 1140px;
    margin-block: 0;
    margin-inline: auto;
    padding: var(--studio-space-5);
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
    min-inline-size: 0;
  }
  @container studio-content (max-width: 760px) {
    .columns { grid-template-columns: minmax(0, 1fr); }
  }
`;
