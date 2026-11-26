/**
 * Native `<dialog>` modals, confirmation modal, non-truncating `.dock-row`,
 * shortcut/MDI picker grids, and HSV color wheel (`D-053`, `D-064`).
 */

import { css } from "../lib/lit.js";

export const DIALOG_STYLES = css`
  dialog.studio-dialog {
    inline-size: min(460px, calc(100vw - 32px));
    max-block-size: calc(100vh - 32px);
    max-block-size: calc(100dvh - 32px);
    padding: var(--studio-space-5);
    border: none;
    border-radius: var(--studio-radius-dialog);
    background: var(--studio-surface);
    color: var(--studio-text);
    box-shadow: var(--studio-overlay-shadow);
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  dialog.studio-dialog::backdrop {
    background: var(--studio-scrim);
    overflow: hidden;
    overscroll-behavior: contain;
  }
  dialog.studio-dialog.confirm-dialog {
    inline-size: min(480px, calc(100vw - 32px));
  }
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .dialog-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .dialog-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height-condensed);
    text-wrap: balance;
  }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-block-start: var(--studio-space-2);
  }
  .dialog-actions.with-secondary {
    justify-content: space-between;
  }
  .dialog-actions-end {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-inline-start: auto;
  }

  dialog.studio-dialog.shortcut-dialog {
    inline-size: min(560px, calc(100vw - 32px));
  }
  dialog.studio-dialog.grid-editor-dialog {
    inline-size: var(--studio-grid-dialog-width);
  }
  dialog.studio-dialog.photo-dialog {
    inline-size: min(680px, calc(100vw - 32px));
  }
  .crop-dropzone {
    inline-size: 100%;
    font: inherit;
    color: inherit;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-5);
    border: 2px dashed var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }
  .crop-dropzone.dragging,
  .crop-dropzone:hover {
    border-color: var(--studio-primary);
    background: var(--studio-dropzone-bg);
  }
  .crop-stage-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface-alt);
  }
  .crop-canvas {
    max-inline-size: 100%;
    block-size: auto;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
    cursor: grab;
    touch-action: none;
    display: block;
  }
  .crop-canvas.dragging {
    cursor: grabbing;
  }
  .crop-canvas:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .crop-canvas.round {
    border-radius: 50%;
  }
  .crop-controls-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    inline-size: 100%;
  }
  .crop-zoom-control {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    flex: 1 1 200px;
  }
  .crop-zoom-control input[type="range"] {
    flex: 1;
    min-inline-size: 120px;
  }
  .crop-filmstrip {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    overflow-x: auto;
    overscroll-behavior-inline: contain;
    padding-block: var(--studio-space-1);
    inline-size: 100%;
  }
  .crop-filmstrip-item {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 2px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    cursor: pointer;
    flex-shrink: 0;
  }
  .crop-filmstrip-item.active {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
  }
  .crop-filmstrip-btn {
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--studio-radius-control);
    cursor: pointer;
    line-height: 0;
  }
  .crop-filmstrip-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .crop-filmstrip-thumb {
    inline-size: 56px;
    block-size: 56px;
    object-fit: cover;
    border-radius: var(--studio-radius-field);
    background: var(--studio-media-bg);
    display: block;
  }
  .crop-filmstrip-remove {
    position: absolute;
    inset-block-start: -6px;
    inset-inline-end: -6px;
    min-inline-size: 24px;
    min-block-size: 24px;
    border-radius: var(--studio-radius-pill);
    border: 1px solid var(--studio-divider);
    background: var(--studio-surface);
    color: var(--studio-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    padding: 0;
    font-size:var(--studio-font-caption);
  }
  .crop-filmstrip-remove:hover {
    background: var(--studio-danger-tonal-bg);
    color: var(--studio-danger-tonal-text);
    border-color: var(--studio-error);
  }
  .media-breadcrumbs {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    padding-block: var(--studio-space-1);
  }
  .media-folder-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--studio-space-2);
  }
  .media-folder-btn {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: var(--studio-text);
    font: inherit;
    text-align: start;
    cursor: pointer;
    min-inline-size: 0;
  }
  .media-folder-btn:hover {
    border-color: var(--studio-primary);
    background: var(--studio-hover);
  }
  .media-folder-btn span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .media-scroll-area {
    max-block-size: 360px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-1);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .photo-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
    gap: var(--studio-space-2);
    max-block-size: 320px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-1);
  }
  .photo-picker-item {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-1);
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: center;
  }
  .photo-picker-item:hover {
    border-color: var(--studio-primary);
  }
  .photo-picker-item.selected {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    box-shadow: var(--studio-photo-ring-selected);
  }
  .photo-picker-thumb {
    inline-size: 88px;
    block-size: 88px;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
  }
  .photo-picker-thumb.circle {
    border-radius: 50%;
  }
  .photo-picker-name {
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    inline-size: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-item-row,
  .dock-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .dock-row {
    flex-wrap: wrap;
  }
  .dock-row .shortcut-item-info {
    flex: 1 1 180px;
  }
  .dock-row .shortcut-item-title,
  .dock-row .shortcut-item-meta {
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .shortcut-item-row.shortcut-item-locked,
  .dock-row.shortcut-item-locked {
    border-style: dashed;
    background: transparent;
  }
  .shortcut-item-row.shortcut-item-locked .shortcut-icon-badge,
  .shortcut-item-row.shortcut-item-hidden .shortcut-icon-badge,
  .dock-row.shortcut-item-locked .shortcut-icon-badge,
  .dock-row.shortcut-item-hidden .shortcut-icon-badge {
    background: var(--studio-surface-alt);
    color: var(--studio-text-secondary);
  }
  .shortcut-icon-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height-compact);
    block-size: var(--studio-control-height-compact);
    border-radius: var(--studio-radius-pill);
    border: 1px solid var(--studio-badge-glass-border);
    background: var(--studio-badge-glass-bg);
    color: var(--studio-badge-glass-fg);
    flex-shrink: 0;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .shortcut-icon-badge.accent-primary {
    background: var(--studio-badge-glass-primary-bg);
    color: var(--studio-badge-glass-primary-fg);
    border-color: var(--studio-badge-glass-primary-border);
  }
  .shortcut-icon-badge.accent-gold {
    background: var(--studio-badge-glass-gold-bg);
    color: var(--studio-badge-glass-gold-fg);
    border-color: var(--studio-badge-glass-gold-border);
  }
  .shortcut-icon-badge.accent-green {
    background: var(--studio-badge-glass-green-bg);
    color: var(--studio-badge-glass-green-fg);
    border-color: var(--studio-badge-glass-green-border);
  }
  .shortcut-icon-badge.accent-red {
    background: var(--studio-badge-glass-red-bg);
    color: var(--studio-badge-glass-red-fg);
    border-color: var(--studio-badge-glass-red-border);
  }
  .shortcut-icon-badge.accent-orange {
    background: var(--studio-badge-glass-orange-bg);
    color: var(--studio-badge-glass-orange-fg);
    border-color: var(--studio-badge-glass-orange-border);
  }
  .shortcut-icon-badge.badge-inverted {
    background: var(--studio-badge-inv-bg);
    color: var(--studio-badge-inv-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-primary {
    background: var(--studio-badge-inv-primary-bg);
    color: var(--studio-badge-inv-primary-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-gold {
    background: var(--studio-badge-inv-gold-bg);
    color: var(--studio-badge-inv-gold-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-green {
    background: var(--studio-badge-inv-green-bg);
    color: var(--studio-badge-inv-green-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-red {
    background: var(--studio-badge-inv-red-bg);
    color: var(--studio-badge-inv-red-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-orange {
    background: var(--studio-badge-inv-orange-bg);
    color: var(--studio-badge-inv-orange-fg);
    border-color: transparent;
  }
  .shortcut-picker-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .shortcut-picker-status {
    flex: 1 1 200px;
    min-inline-size: 0;
  }
  .shortcut-style-filter {
    flex-shrink: 0;
  }
  .shortcut-badge-style {
    align-self: flex-start;
  }
  .shortcut-accent-pills {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
  }
  .accent-pill-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .accent-pill-btn:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  .accent-pill-btn[aria-checked="true"] {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
  }
  .accent-swatch-dot {
    inline-size: var(--studio-swatch-dot-size);
    block-size: var(--studio-swatch-dot-size);
    border-radius: var(--studio-radius-pill);
    border: 1px solid transparent;
    flex-shrink: 0;
  }
  .accent-swatch-dot.swatch-default {
    background: var(--studio-badge-glass-bg);
    border-color: var(--studio-text-secondary);
  }
  .accent-swatch-dot.swatch-primary {
    background: var(--studio-accent-dot-primary);
  }
  .accent-swatch-dot.swatch-gold {
    background: var(--studio-accent-dot-gold);
  }
  .accent-swatch-dot.swatch-green {
    background: var(--studio-accent-dot-green);
  }
  .accent-swatch-dot.swatch-red {
    background: var(--studio-accent-dot-red);
  }
  .accent-swatch-dot.swatch-orange {
    background: var(--studio-accent-dot-orange);
  }
  .shortcut-item-info {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1;
  }
  .shortcut-item-title {
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-item-meta {
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row input[type="text"] {
    flex: 1;
    min-inline-size: 0;
  }
  .mdi-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: var(--studio-space-1);
    max-block-size: 168px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .mdi-picker-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-block-size: var(--studio-control-height);
    border: 1px solid transparent;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    cursor: pointer;
  }
  .mdi-picker-btn:hover { background: var(--studio-hover); }
  .mdi-picker-btn.selected {
    background: var(--studio-chip-primary-bg);
    border-color: var(--studio-primary);
    color: var(--studio-chip-primary-text);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input[type="text"] {
    inline-size: 120px;
    font-family: var(--studio-font-code);
    text-align: center;
  }
  .color-hex-row input[type="color"] {
    inline-size: var(--studio-control-height);
    block-size: var(--studio-control-height);
    padding: 0;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: none;
    cursor: pointer;
  }

  /* Visual Pinned Tile-Grid Page Editor (D-086) */
  .pinned-grid-editor {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .pinned-page-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pinned-page-tabs {
    display: flex;
    align-items: center;
    flex-wrap: nowrap;
    overflow-x: auto;
    scroll-padding-inline: var(--studio-space-1);
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1 1 auto;
  }
  .pinned-page-tab {
    min-block-size: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: var(--studio-grid-border-w) solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .pinned-page-tab:hover {
    background: var(--studio-hover);
    color: var(--studio-text);
  }
  .pinned-page-tab.active,
  .pinned-page-tab[aria-selected="true"] {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
    border-color: var(--studio-primary);
  }
  .pinned-page-bar-end {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    flex-shrink: 0;
  }
  .pinned-page-controls {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pinned-page-title-field {
    flex: 1 1 auto;
    min-inline-size: 0;
  }
  .pinned-reflow-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pinned-grid-canvas {
    position: relative;
    display: grid;
    grid-template-columns: repeat(var(--grid-cols, 2), minmax(0, 1fr));
    grid-template-rows: repeat(var(--grid-rows, 3), minmax(var(--studio-grid-cell-min-h), 1fr));
    gap: var(--studio-space-2);
    inline-size: 100%;
    max-inline-size: var(--studio-grid-canvas-max-w);
    margin-inline: auto;
    padding: var(--studio-space-3);
    border: var(--studio-grid-border-w) solid var(--studio-divider);
    border-radius: var(--studio-radius-card);
    background: var(--studio-surface-alt);
    user-select: none;
  }
  .pinned-grid-canvas.is-round::after {
    content: "";
    position: absolute;
    inset: var(--studio-space-1);
    border: var(--studio-grid-border-strong-w) dashed var(--studio-grid-round-ring);
    border-radius: 50%;
    pointer-events: none;
  }
  .pinned-grid-slot-guide {
    grid-column: var(--grid-col) / span 1;
    grid-row: var(--grid-row) / span 1;
    border: var(--studio-grid-border-w) dashed var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: transparent;
    pointer-events: none;
    z-index: 1;
  }
  .pinned-grid-empty-cell {
    grid-column: var(--grid-col) / span 1;
    grid-row: var(--grid-row) / span 1;
    z-index: 2;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-block-size: var(--studio-grid-cell-min-h);
    padding: var(--studio-space-2);
    border: var(--studio-grid-border-w) dashed var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    cursor: pointer;
    transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
  }
  .pinned-grid-empty-cell:hover:not(:disabled) {
    border-color: var(--studio-primary);
    background: var(--studio-grid-empty-hover-bg);
    color: var(--studio-primary);
  }
  .pinned-grid-empty-cell:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .pinned-grid-tile {
    grid-column: var(--grid-col) / span var(--grid-w, 1);
    grid-row: var(--grid-row) / span var(--grid-h, 1);
    z-index: 3;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-inline-size: 0;
    min-block-size: var(--studio-grid-cell-min-h);
    padding: var(--studio-space-2);
    border: var(--studio-grid-border-w) solid var(--studio-badge-glass-border);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface);
    color: var(--studio-text);
    cursor: grab;
    touch-action: none;
    transition: border-color 0.15s ease, opacity 0.15s ease, background-color 0.15s ease;
  }
  .pinned-grid-tile:hover,
  .pinned-grid-tile:focus-visible {
    border-color: var(--studio-primary);
  }
  .pinned-grid-tile.is-dragging {
    opacity: 0.65;
    cursor: grabbing;
    z-index: 5;
    transform: translate3d(var(--drag-x, 0px), var(--drag-y, 0px), 0);
    will-change: transform;
    transition: none;
  }
  .pinned-grid-tile.tile-accent-primary {
    border-color: var(--studio-badge-glass-primary-border);
  }
  .pinned-grid-tile.tile-accent-gold {
    border-color: var(--studio-badge-glass-gold-border);
  }
  .pinned-grid-tile.tile-accent-green {
    border-color: var(--studio-badge-glass-green-border);
  }
  .pinned-grid-tile.tile-accent-red {
    border-color: var(--studio-badge-glass-red-border);
  }
  .pinned-grid-tile.tile-accent-orange {
    border-color: var(--studio-badge-glass-orange-border);
  }
  .pinned-grid-tile.tile-inverted {
    background: var(--studio-badge-inv-bg);
    color: var(--studio-badge-inv-fg);
    border-color: transparent;
  }
  .pinned-grid-tile.tile-inverted.tile-accent-primary {
    background: var(--studio-badge-inv-primary-bg);
    color: var(--studio-badge-inv-primary-fg);
  }
  .pinned-grid-tile.tile-inverted.tile-accent-gold {
    background: var(--studio-badge-inv-gold-bg);
    color: var(--studio-badge-inv-gold-fg);
  }
  .pinned-grid-tile.tile-inverted.tile-accent-green {
    background: var(--studio-badge-inv-green-bg);
    color: var(--studio-badge-inv-green-fg);
  }
  .pinned-grid-tile.tile-inverted.tile-accent-red {
    background: var(--studio-badge-inv-red-bg);
    color: var(--studio-badge-inv-red-fg);
  }
  .pinned-grid-tile.tile-inverted.tile-accent-orange {
    background: var(--studio-badge-inv-orange-bg);
    color: var(--studio-badge-inv-orange-fg);
  }
  .pinned-tile-top-bar {
    position: absolute;
    inset-block-start: var(--studio-space-1);
    inset-inline: var(--studio-space-1);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-1);
    pointer-events: none;
  }
  .pinned-tile-meta-badges {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
  }
  .pinned-tile-span-badge {
    display: inline-flex;
    align-items: center;
    padding-block: 0;
    padding-inline: var(--studio-space-1);
    border-radius: var(--studio-radius-field);
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height);
  }
  .pinned-tile-confirm-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: currentColor;
    opacity: 0.85;
  }
  .pinned-tile-actions {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    pointer-events: auto;
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  .pinned-grid-tile:hover .pinned-tile-actions,
  .pinned-grid-tile:focus-within .pinned-tile-actions,
  .pinned-grid-tile:focus-visible .pinned-tile-actions {
    opacity: 1;
  }
  @media (hover: none) {
    .pinned-tile-actions {
      opacity: 1;
    }
  }
  .pinned-tile-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-grid-tile-action-size);
    block-size: var(--studio-grid-tile-action-size);
    padding: 0;
    border: var(--studio-grid-border-w) solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface);
    color: var(--studio-text);
    cursor: pointer;
  }
  .pinned-tile-action-btn:hover {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
    border-color: var(--studio-primary);
  }
  .pinned-tile-action-btn.danger:hover {
    background: var(--studio-danger-tonal-bg);
    color: var(--studio-danger-tonal-text);
    border-color: var(--studio-error);
  }
  .pinned-tile-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    text-align: center;
    min-inline-size: 0;
    padding-block-start: var(--studio-space-2);
  }
  .pinned-tile-label {
    max-inline-size: 100%;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pinned-tile-sub {
    max-inline-size: 100%;
    font-size:var(--studio-font-caption);
    opacity: 0.78;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pinned-tile-resize-handle {
    position: absolute;
    inset-block-end: 0;
    inset-inline-end: 0;
    display: inline-flex;
    align-items: flex-end;
    justify-content: flex-end;
    inline-size: var(--studio-grid-resize-size);
    block-size: var(--studio-grid-resize-size);
    padding: var(--studio-space-1);
    border: none;
    border-radius: var(--studio-radius-field);
    background: transparent;
    color: currentColor;
    cursor: nwse-resize;
    touch-action: none;
    opacity: 0.55;
    transition: opacity 0.15s ease;
  }
  .pinned-tile-resize-handle::after {
    content: "";
    inline-size: var(--studio-grid-resize-grip);
    block-size: var(--studio-grid-resize-grip);
    border-inline-end: var(--studio-grid-border-strong-w) solid currentColor;
    border-block-end: var(--studio-grid-border-strong-w) solid currentColor;
    border-end-end-radius: var(--studio-radius-field);
  }
  :host(:dir(rtl)) .pinned-tile-resize-handle {
    cursor: nesw-resize;
  }
  .pinned-grid-tile:hover .pinned-tile-resize-handle,
  .pinned-grid-tile:focus-within .pinned-tile-resize-handle,
  .pinned-tile-resize-handle:focus-visible {
    opacity: 1;
  }
  .pinned-grid-ghost {
    grid-column: var(--grid-col) / span var(--grid-w, 1);
    grid-row: var(--grid-row) / span var(--grid-h, 1);
    z-index: 4;
    border-radius: var(--studio-radius-control);
    pointer-events: none;
  }
  .pinned-grid-ghost.valid {
    border: var(--studio-grid-border-strong-w) dashed var(--studio-grid-ghost-valid-border);
    background: var(--studio-grid-ghost-valid-bg);
  }
  .pinned-grid-ghost.invalid {
    border: var(--studio-grid-border-strong-w) dashed var(--studio-grid-ghost-invalid-border);
    background: var(--studio-grid-ghost-invalid-bg);
  }
  .pinned-grid-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pinned-grid-count {
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
  }

  /* Shortcut Modal Tile Layout Section (D-086) */
  .shortcut-tile-layout {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
    border-block-start: var(--studio-grid-border-w) solid var(--studio-divider);
  }
  .shortcut-tile-layout-row {
    display: flex;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: var(--studio-space-4);
  }
  .shortcut-span-field {
    flex: 0 0 auto;
  }
  .shortcut-span-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
  }
  .shortcut-page-field {
    flex: 1 1 auto;
    min-inline-size: 0;
  }
  .span-matrix {
    display: grid;
    grid-template-columns: repeat(var(--grid-cols, 2), var(--studio-span-cell-size));
    grid-template-rows: repeat(var(--grid-rows, 3), var(--studio-span-cell-size));
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: var(--studio-grid-border-w) solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    inline-size: max-content;
  }
  .span-matrix-cell {
    inline-size: var(--studio-span-cell-size);
    block-size: var(--studio-span-cell-size);
    padding: 0;
    border: var(--studio-grid-border-w) solid var(--studio-divider);
    border-radius: var(--studio-span-cell-radius);
    background: var(--studio-surface);
    cursor: pointer;
    transition: background-color 0.12s ease, border-color 0.12s ease;
  }
  .span-matrix-cell.hovered {
    background: var(--studio-primary-tint);
    border-color: var(--studio-primary);
  }
  .span-matrix-cell.selected {
    background: var(--studio-btn-tonal-bg);
    border-color: var(--studio-primary);
  }
  .span-matrix-cell.would-reflow {
    border-style: dashed;
    border-color: var(--studio-warning);
  }
`;
