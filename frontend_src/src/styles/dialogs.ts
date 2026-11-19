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
