/**
 * Settings rows, form controls, RTL switches, buttons, WAI-ARIA combobox (`Q11`),
 * and pointer/keyboard sortable drag-and-drop rows (`U4`).
 */

import { css } from "../lib/lit.js";

export const CONTROL_STYLES = css`
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
    padding-block: var(--studio-space-2);
    padding-inline: 0;
  }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
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
  .settings-row-control .combobox,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="search"],
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] {
    inline-size: 260px;
    max-inline-size: 100%;
  }
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] { inline-size: 140px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; inline-size: auto; }

  select,
  input[type="text"],
  input[type="search"],
  input[type="number"],
  input[type="time"],
  input[type="password"],
  textarea {
    min-height: var(--studio-control-height);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-block-end: 1px solid var(--studio-field-line);
    border-radius: var(--studio-radius-field) var(--studio-radius-field) 0 0;
    background: var(--studio-field-bg);
    color: var(--studio-text);
    color-scheme: inherit;
    font: inherit;
    transition: background-color 0.15s ease-out;
  }
  textarea {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    resize: vertical;
  }
  select:hover,
  input[type="text"]:hover,
  input[type="search"]:hover,
  input[type="number"]:hover,
  input[type="time"]:hover,
  input[type="password"]:hover,
  textarea:hover {
    background: var(--studio-field-bg-hover);
  }
  select option, select optgroup {
    background-color: var(--studio-popup-bg);
    color: var(--studio-text);
  }
  input::placeholder, textarea::placeholder {
    color: var(--studio-text-secondary);
    opacity: 1;
  }
  input[readonly] { color: var(--studio-text-secondary); }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { inline-size: 140px; accent-color: var(--studio-primary); }

  select:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  button:focus-visible,
  a:focus-visible,
  summary:focus-visible,
  [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  select:focus-visible,
  input[type="text"]:focus-visible,
  input[type="search"]:focus-visible,
  input[type="number"]:focus-visible,
  input[type="time"]:focus-visible,
  input[type="password"]:focus-visible,
  textarea:focus-visible {
    outline: none;
    border-block-end-color: var(--studio-primary);
    box-shadow: inset 0 -1px 0 var(--studio-primary);
  }

  /* RTL-safe toggle switch */
  .switch {
    appearance: none;
    position: relative;
    inline-size: 48px;
    block-size: 24px;
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
    inset-block-start: 2px;
    inset-inline-start: 2px;
    inline-size: 18px;
    block-size: 18px;
    border-radius: 50%;
    background: var(--studio-switch-thumb);
    box-shadow: var(--studio-switch-thumb-shadow);
    transition: transform 0.15s ease, background-color 0.15s ease;
  }
  .switch:checked {
    background: var(--studio-switch-on-track);
    border-color: var(--studio-switch-on-border);
  }
  .switch:checked::after {
    transform: translateX(24px);
    background: var(--studio-switch-on-thumb);
  }
  :host(:dir(rtl)) .switch:checked::after {
    transform: translateX(-24px);
  }
  .switch:disabled { opacity: 0.3; cursor: not-allowed; }

  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input:not([type="file"]),
  .input-action-row > select,
  .input-action-row > .combobox {
    flex: 1 1 180px;
    min-inline-size: 0;
  }
  .input-action-row > input[type="file"] { flex: 0 1 auto; max-inline-size: 100%; }

  .segmented {
    display: inline-flex;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
  }
  .segmented button {
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .segmented button[aria-checked="true"] {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .inline-switch {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
    cursor: pointer;
    white-space: nowrap;
  }
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
    min-inline-size: 0;
  }
  .list-row-grow { flex: 1; min-inline-size: 0; }
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
    min-inline-size: 0;
  }
  .stacked-field > label, .stacked-field > .field-label {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .stacked-field > select,
  .stacked-field > input,
  .stacked-field > .combobox { inline-size: 100%; }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height);
    padding-block: 0;
    padding-inline: var(--studio-space-4);
    border: none;
    border-radius: var(--studio-radius-button);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    line-height: 1;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease-out;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-btn-accent-bg); color: var(--studio-btn-accent-text); }
  .btn-primary:hover:not(:disabled) { background: var(--studio-btn-accent-bg-hover); }
  .btn-secondary { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .btn-secondary:hover:not(:disabled) { background: var(--studio-btn-tonal-bg-hover); }
  .btn-text {
    background: transparent;
    color: var(--studio-btn-tonal-text);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
  }
  .btn-text:hover:not(:disabled) { background: var(--studio-btn-plain-hover); }
  .btn-danger { background: var(--studio-danger-tonal-bg); color: var(--studio-danger-tonal-text); }
  .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
  .btn-danger-filled { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height);
    block-size: var(--studio-control-height);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .btn-icon:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-icon:hover:not(:disabled) { background: var(--studio-hover); }
  .btn-icon.danger { color: var(--studio-error); }
  .btn-icon svg { inline-size: 20px; block-size: 20px; fill: currentColor; }

  .quick-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
    padding-block-end: var(--studio-space-3);
    border-block-end: 1px solid var(--studio-divider);
  }
  .quick-action-grid:last-child {
    padding-block-end: 0;
    border-block-end: none;
  }
  .quick-action-btn {
    justify-content: flex-start;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border-radius: var(--studio-radius-control);
    white-space: normal;
    text-align: start;
    line-height: var(--studio-line-height-condensed);
  }
  .quick-action-btn svg {
    inline-size: 18px;
    block-size: 18px;
    fill: currentColor;
    flex-shrink: 0;
  }

  /* WAI-ARIA 1.2 searchable entity combobox (Q11) */
  .combobox {
    position: relative;
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
  }
  .combobox-input-wrap {
    position: relative;
    display: flex;
    align-items: center;
    inline-size: 100%;
  }
  .combobox-input-wrap > input[role="combobox"] {
    inline-size: 100%;
    padding-inline-end: calc(var(--studio-control-height-compact) + var(--studio-space-2));
  }
  .combobox-clear {
    position: absolute;
    inset-inline-end: var(--studio-space-1);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height-compact);
    block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .combobox-clear:hover {
    background: var(--studio-hover);
    color: var(--studio-text);
  }
  .combobox-listbox {
    position: absolute;
    inset-block-start: calc(100% + var(--studio-space-1));
    inset-inline: 0;
    z-index: 45;
    max-height: 280px;
    margin: 0;
    padding: var(--studio-space-1);
    list-style: none;
    overflow-y: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-popup-bg);
    box-shadow: var(--studio-overlay-shadow);
  }
  .combobox-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-1);
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-field);
    cursor: pointer;
  }
  .combobox-option:hover,
  .combobox-option.active {
    background: var(--studio-hover);
  }
  .combobox-option[aria-selected="true"] {
    background: var(--studio-nav-active-bg);
    color: var(--studio-nav-active-text);
  }
  .combobox-option-main {
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
    flex: 1;
  }
  .combobox-option-title {
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .combobox-option-id {
    color: var(--studio-text-secondary);
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-caption);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .combobox-option-chips {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    flex-shrink: 0;
  }
  .combobox-empty,
  .combobox-footer {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
  }
  .combobox-footer {
    border-block-start: 1px solid var(--studio-divider);
  }

  /* Pointer drag-and-drop & keyboard sortable rows (U4) */
  .sortable-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }
  .sortable-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    transition: border-color 0.12s ease, opacity 0.12s ease, background-color 0.12s ease;
  }
  .sortable-row.dragging,
  .pill.dragging {
    opacity: 0.65;
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
  }
  .sortable-row.drag-over-before {
    border-block-start: 2px solid var(--studio-primary);
  }
  .sortable-row.drag-over-after {
    border-block-end: 2px solid var(--studio-primary);
  }
  .pill.drag-over-before {
    box-shadow: inset 2px 0 0 var(--studio-primary);
  }
  .pill.drag-over-after {
    box-shadow: inset -2px 0 0 var(--studio-primary);
  }
  .drag-handle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-field);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    line-height: 1;
    cursor: grab;
    touch-action: none;
    user-select: none;
    flex-shrink: 0;
  }
  .drag-handle:hover {
    background: var(--studio-hover);
    color: var(--studio-text);
  }
  .drag-handle:active {
    cursor: grabbing;
  }
  .sortable-row-content {
    flex: 1;
    min-inline-size: 0;
  }
  .sortable-row-actions {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    flex-shrink: 0;
  }
  .sortable-row-stacked {
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-3);
  }
  .sortable-row-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    inline-size: 100%;
  }
  .sortable-row-title {
    flex: 1 1 auto;
    min-inline-size: 0;
  }
  .sortable-row-stacked > .sortable-row-content {
    inline-size: 100%;
  }
  .sortable-row-stacked .combobox-option-title {
    white-space: normal;
    line-height: 1.3;
  }
`;
