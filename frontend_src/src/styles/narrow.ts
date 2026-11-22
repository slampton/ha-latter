/**
 * Container queries & mobile breakpoints, including horizontal `.nav-list` scroll fade mask.
 */

import { css } from "../lib/lit.js";

export const NARROW_STYLES = css`
  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-block-start: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select,
    .settings-row-control .combobox,
    .settings-row-control input[type="text"],
    .settings-row-control input[type="search"],
    .settings-row-control input[type="password"] {
      inline-size: 100%;
    }
  }
  @container (max-width: 360px) {
    .quick-action-grid { grid-template-columns: minmax(0, 1fr); }
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
      scrollbar-width: none;
      padding-inline: var(--studio-space-1);
      -webkit-mask-image: var(--studio-nav-scroll-mask);
      mask-image: var(--studio-nav-scroll-mask);
    }
    .nav-list::-webkit-scrollbar { display: none; }
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
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-block-start: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select,
    .settings-row-control .combobox,
    .settings-row-control input[type="text"],
    .settings-row-control input[type="search"],
    .settings-row-control input[type="password"] {
      inline-size: 100%;
    }
  }
  @media (max-width: 480px) {
    .list-row { flex-wrap: wrap; }
    .list-row-head { flex-wrap: wrap; }
    .list-row-main { grid-template-columns: minmax(0, 1fr); inline-size: 100%; }
  }
`;
