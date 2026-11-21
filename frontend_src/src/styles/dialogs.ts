/**
 * Native `<dialog>` modals, confirmation modal (`Q5`), non-truncating `.dock-row`,
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
  dialog.studio-dialog::backdrop { background: var(--studio-scrim); }
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
  dialog.studio-dialog.photo-dialog {
    inline-size: min(680px, calc(100vw - 32px));
  }
  .crop-dropzone {
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
    inline-size: 24px;
    block-size: 24px;
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
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
    flex-shrink: 0;
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
  .shortcut-page-group {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface-alt);
  }
  .shortcut-page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    color: var(--studio-text-secondary);
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
    block-size: var(--studio-control-height);
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
`;
