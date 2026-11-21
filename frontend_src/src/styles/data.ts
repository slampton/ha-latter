/**
 * Key-value lists, data tables, WCAG 2.2 AA chips, >= 32px pills, BLE signal bars,
 * wallpaper gallery, camera previews, logs, & alerts (`D-061`, `D-064`).
 */

import { css } from "../lib/lit.js";

export const DATA_STYLES = css`
  .kv-list { display: flex; flex-direction: column; gap: 0; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-1);
    padding-inline: 0;
  }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: end;
  }
  button.kv-row {
    inline-size: 100%;
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: start;
    cursor: pointer;
  }
  button.kv-row:hover { background: var(--studio-hover); }
  button.kv-row > strong::after {
    content: " ›";
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  :host(:dir(rtl)) button.kv-row > strong::after {
    content: " ‹";
  }

  .table-wrap {
    inline-size: 100%;
    overflow-x: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  table.data-table {
    inline-size: 100%;
    border-collapse: collapse;
    text-align: start;
  }
  table.data-table th {
    padding: 0;
    border-block-end: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  .sort-btn {
    inline-size: 100%;
    padding: var(--studio-space-3);
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: start;
    cursor: pointer;
  }
  .sort-btn:hover { color: var(--studio-text); }
  th[aria-sort="ascending"] .sort-btn,
  th[aria-sort="descending"] .sort-btn {
    color: var(--studio-primary);
  }
  table.data-table td {
    padding: var(--studio-space-3);
    border-block-end: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  table.data-table tbody tr:last-child td { border-block-end: none; }
  table.data-table tbody tr { cursor: pointer; }
  table.data-table tbody tr:hover,
  table.data-table tbody tr:focus-visible {
    background: var(--studio-hover);
  }
  td.col-name { font-weight: var(--studio-weight-medium); }
  table.data-table a { color: inherit; text-decoration: none; }
  table.data-table a:hover { text-decoration: underline; }
  td.col-open { color: var(--studio-text-secondary); text-align: end; }

  /* WCAG 2.2 AA >= 4.5:1 semantic chips */
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: 22px;
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .chip-primary {
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .chip-success {
    background: var(--studio-chip-success-bg);
    color: var(--studio-chip-success-text);
  }
  .chip-warning {
    background: var(--studio-chip-warning-bg);
    color: var(--studio-chip-warning-text);
  }
  .chip-error {
    background: var(--studio-chip-danger-bg);
    color: var(--studio-chip-danger-text);
  }
  .status-dot {
    display: inline-block;
    inline-size: 8px;
    block-size: 8px;
    margin-inline-end: var(--studio-space-2);
    border-radius: 50%;
    background: var(--studio-text-disabled);
  }
  .chip > .status-dot { margin-inline-end: var(--studio-space-1); }
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }

  .status-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
  }
  @container (max-width: 260px) {
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
    text-align: start;
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
    inline-size: 16px;
    block-size: 16px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .status-tile-value {
    margin-block-start: var(--studio-space-1);
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
  .status-tile > .signal-track { margin-block-start: var(--studio-space-1); }
  @container (max-width: 420px) {
    .status-tile {
      gap: 0;
      padding-block: var(--studio-space-2);
      padding-inline: var(--studio-space-3);
    }
    .status-tile-head { gap: var(--studio-space-1); }
    .status-tile-value {
      margin-block-start: var(--studio-space-1);
      font-size:var(--studio-font-body);
    }
    .status-tile-meta {
      margin-block-start: var(--studio-space-1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .overview-box {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-2);
    inline-size: 100%;
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: start;
  }
  button.overview-box {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.overview-box:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  .overview-box-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .overview-box-title {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .overview-box-title svg {
    inline-size: 18px;
    block-size: 18px;
    fill: currentColor;
    color: var(--studio-text-secondary);
    flex-shrink: 0;
  }
  .overview-box-end {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .overview-box-chevron {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .overview-box-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }

  /* >= 32px WCAG 2.2 AA pill targets & sortable pills */
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
  }
  .pill.enabled {
    border-color: var(--studio-primary);
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .pill-move {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-move:hover:not(:disabled) {
    background: var(--studio-hover);
    color: var(--studio-primary);
  }
  .pill-move:disabled { opacity: 0.4; cursor: not-allowed; }
  .pill-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .pill .drag-handle {
    border-radius: var(--studio-radius-pill);
    color: inherit;
  }

  .swatch {
    display: inline-block;
    inline-size: 20px;
    block-size: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* BLE rows & upload progress */
  #card-ble-calibration {
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
  }
  .calibrate-target-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .calibrate-target-box.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
    background: var(--studio-primary-tint);
  }
  .calibrate-handoff-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-weight: var(--studio-weight-medium);
  }
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
  .proxy-trim-details { padding-block-start: var(--studio-space-2); }
  .proxy-trim-details > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .proxy-trim-details[open] > summary,
  .proxy-trim-details > summary:hover {
    color: var(--studio-text);
  }
  .proxy-trim-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
  }
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
    block-size: 6px;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface-alt);
    overflow: hidden;
  }
  .signal-fill {
    inline-size: var(--signal-pct, 0%);
    block-size: 100%;
    background: var(--studio-primary);
    transition: inline-size 0.25s ease, width 0.25s ease;
  }
  .signal-fill.low { background: var(--studio-error); }
  .upload-progress-fill {
    inline-size: var(--upload-pct, 0%);
    block-size: 100%;
    background: var(--studio-primary);
    transition: inline-size 0.15s ease, width 0.15s ease;
  }

  /* Wallpapers, camera previews & logs */
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
    inline-size: 104px;
    block-size: 104px;
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
    margin-block-start: auto;
    inline-size: 100%;
  }
  .btn-icon.wp-star-btn {
    inline-size: var(--studio-control-height-compact);
    block-size: var(--studio-control-height-compact);
  }
  .btn-icon.wp-star-btn:hover {
    color: var(--studio-warning);
    background: var(--studio-warning-tint);
  }
  .btn-icon.wp-star-btn.starred {
    color: var(--studio-warning);
  }

  /* Photo Library, Collection Filter Strip, Bulk Toolbar & Compact Pool Previews (D-072) */
  .photo-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .photo-toolbar-start,
  .photo-toolbar-end {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .photo-search-input {
    min-inline-size: 200px;
    flex: 1 1 220px;
  }
  .collection-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .collection-chip-wrap {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
  }
  .collection-chip-wrap.active {
    border-color: var(--studio-primary);
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .collection-chip-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .collection-chip-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: 28px;
    min-block-size: 28px;
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    cursor: pointer;
  }
  .collection-chip-action:hover {
    background: var(--studio-hover);
  }
  .collection-chip-action svg {
    inline-size: 14px;
    block-size: 14px;
    fill: currentColor;
  }
  .photo-bulk-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-primary);
    border-radius: var(--studio-radius-control);
    background: var(--studio-primary-tint);
  }
  .photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
    gap: var(--studio-space-3);
  }
  .photo-grid > .empty-state {
    grid-column: 1 / -1;
  }
  .photo-tile {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    content-visibility: auto;
    contain-intrinsic-size: 180px 220px;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
  }
  .photo-tile:hover {
    border-color: var(--studio-primary);
  }
  .photo-tile.selected {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    box-shadow: var(--studio-photo-ring-selected);
  }
  .photo-tile-thumb-btn {
    position: relative;
    display: block;
    inline-size: 100%;
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
    overflow: hidden;
    cursor: pointer;
    aspect-ratio: 1 / 1;
    line-height: 0;
  }
  .photo-tile-thumb-btn.circle {
    border-radius: 50%;
  }
  .photo-tile-thumb-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .photo-tile-img {
    inline-size: 100%;
    block-size: 100%;
    object-fit: cover;
    display: block;
  }
  .photo-tile-check {
    position: absolute;
    inset-block-start: var(--studio-space-2);
    inset-inline-start: var(--studio-space-2);
    z-index: 2;
    inline-size: 20px;
    block-size: 20px;
    accent-color: var(--studio-primary);
    cursor: pointer;
  }
  .photo-tile-badge {
    position: absolute;
    inset-block-end: var(--studio-space-1);
    inset-inline-end: var(--studio-space-1);
    padding-block: 2px;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-photo-badge-bg);
    color: var(--studio-photo-badge-text);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .photo-tile-meta {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .photo-tile-name {
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .photo-tile-sub {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
  }
  .photo-pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  .photo-pool-preview {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .photo-pool-thumbs {
    display: flex;
    align-items: center;
    gap: var(--studio-space-1);
    flex-shrink: 0;
  }
  .photo-pool-thumb {
    inline-size: 48px;
    block-size: 48px;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
  }
  .photo-pool-thumb.circle {
    border-radius: 50%;
  }
  .photo-pool-info {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1 1 160px;
  }
  .photo-pool-title {
    font-weight: var(--studio-weight-medium);
    overflow-wrap: break-word;
  }
  .photo-pool-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    overflow-wrap: break-word;
  }
  .photo-pool-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    flex-shrink: 0;
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
    inline-size: 100%;
    max-inline-size: 360px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
  }
  .log-output {
    max-block-size: 380px;
    margin: 0;
    padding: var(--studio-space-3);
    overflow: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    white-space: pre-wrap;
  }

  /* Empty, loading, alerts, toast, & shadow-safe offscreen helpers */
  .empty-state {
    padding-block: var(--studio-space-3);
    padding-inline: 0;
    color: var(--studio-text-secondary);
  }
  .loading-state {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    padding-block: var(--studio-space-5);
    padding-inline: 0;
    color: var(--studio-text-secondary);
  }
  .loading-state::before {
    content: "";
    inline-size: 20px;
    block-size: 20px;
    border: 2px solid var(--studio-divider);
    border-block-start-color: var(--studio-primary);
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
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-info-tint);
  }
  .alert-error { background: var(--studio-error-tint); }
  .alert-warning { background: var(--studio-warning-tint); }
  .alert-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .alert-list {
    margin: 0;
    padding-inline-start: var(--studio-space-5);
  }
  .toast {
    position: fixed;
    inset-inline-start: 50%;
    inset-block-end: var(--studio-space-5);
    transform: translateX(-50%);
    z-index: 50;
    max-inline-size: min(560px, calc(100vw - 32px));
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-toast-bg);
    color: var(--studio-toast-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  .toast.error { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .offscreen,
  .sr-only {
    position: fixed;
    inset-block-start: 0;
    inset-inline-start: 0;
    inline-size: 1px;
    block-size: 1px;
    padding: 0;
    margin: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: none;
    opacity: 0;
    pointer-events: none;
  }
`;
