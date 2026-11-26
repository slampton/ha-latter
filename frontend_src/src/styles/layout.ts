/**
 * Title bar, two-pane RTL-safe sidebar shell, navigation badges, & two-column layout (`D-014`).
 */

import { css } from "../lib/lit.js";

export const LAYOUT_STYLES = css`
  .skip-link {
    position: fixed;
    inset-block-start: -100px;
    inset-inline-start: var(--studio-space-3);
    z-index: 60;
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-4);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-btn-accent-bg);
    color: var(--studio-btn-accent-text);
    font-weight: var(--studio-weight-medium);
    text-decoration: none;
    box-shadow: var(--studio-overlay-shadow);
  }
  .skip-link:focus-visible {
    inset-block-start: var(--studio-space-2);
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }

  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-block-size: var(--studio-header-height);
    padding-block: var(--studio-space-1);
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
    min-inline-size: 0;
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
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: var(--studio-control-height-compact);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-decoration: none;
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
    min-inline-size: 0;
  }
  .page-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
    text-wrap: balance;
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
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .titlebar-title { padding-inline-start: 0; }
    .app-shell { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto 1fr; }
    aside.sidebar {
      align-self: start;
      position: sticky;
      inset-block-start: var(--studio-header-height);
      z-index: 25;
      block-size: auto;
      padding-block: var(--studio-space-2);
      padding-inline: var(--studio-space-3);
      border-inline-end: none;
      border-block-end: 1px solid var(--studio-divider);
    }
    .nav-device-title { display: none; }
    .nav-list {
      flex-direction: row;
      overflow-x: auto;
      scroll-padding-inline: var(--studio-space-2);
      padding-block: var(--studio-space-1);
      padding-inline: var(--studio-space-1);
    }
    .nav-btn {
      inline-size: auto;
      border: 1px solid var(--studio-divider);
      border-radius: var(--studio-radius-pill);
    }
    #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-inline-start: var(--studio-space-3); }
    .content-wrap {
      padding-block: var(--studio-space-4) var(--studio-space-5);
      padding-inline: var(--studio-space-3);
    }
    :host {
      scroll-padding-block-start: calc(var(--studio-header-height) + var(--studio-space-5) * 4);
    }
  }
`;
