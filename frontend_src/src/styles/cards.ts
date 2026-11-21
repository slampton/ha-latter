/**
 * Card surfaces, collapsible drawers, Home Hub domain boxes, & Area presence containers.
 */

import { css } from "../lib/lit.js";

export const CARD_STYLES = css`
  .card {
    min-inline-size: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: var(--studio-card-border-width) solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
    color: var(--studio-text);
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .card.danger { border-color: var(--studio-error); }
  .card.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-card-handoff-shadow);
    background: var(--studio-handoff-surface);
  }
  .handoff-active[tabindex="-1"]:focus-visible { outline: none; }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding-block: var(--studio-space-card-top) 0;
    padding-inline: var(--studio-space-4);
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    min-inline-size: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    letter-spacing: var(--studio-card-title-tracking);
    line-height: var(--studio-line-height-condensed);
  }
  .card-subtitle, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
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
    padding: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-block-end: var(--studio-space-card-top);
  }
  details.card > summary::-webkit-details-marker { display: none; }
  details.card > summary::after {
    content: "▾";
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.card[open] > summary::after { transform: rotate(180deg); }
  details.card[open] > summary { border-block-end: 1px solid var(--studio-divider); }
  details.sub-collapsible {
    border-block-start: 1px solid var(--studio-divider);
    padding-block-start: var(--studio-space-3);
  }
  details.sub-collapsible > summary {
    cursor: pointer;
    font-weight: var(--studio-weight-medium);
  }
  details.sub-collapsible > .card-content {
    padding-block: var(--studio-space-3) 0;
    padding-inline: 0;
  }
  details.sub-collapsible.summary-row > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    list-style: none;
  }
  details.sub-collapsible.summary-row > summary::-webkit-details-marker { display: none; }
  .summary-row-end {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .summary-chevron {
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.sub-collapsible.summary-row[open] > summary .summary-chevron {
    transform: rotate(180deg);
  }
  .hub-domain-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .hub-domain-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height-compact);
  }
  .hub-domain-title {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-weight: var(--studio-weight-medium);
  }
  .hub-domain-title svg {
    width: 18px;
    height: 18px;
    fill: var(--studio-primary);
    flex-shrink: 0;
  }
  .hub-domain-empty {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .hub-slot-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  .hub-slot-row > select {
    flex: 1 1 200px;
    min-inline-size: 0;
    max-inline-size: 100%;
  }
  .hub-slot-meta {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
  }
  .area-presence-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .area-presence-box.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
    background: var(--studio-primary-tint);
  }
  .area-box-head {
    display: flex;
    align-items: safe center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-heading {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-title {
    flex: 1 1 140px;
    min-inline-size: 0;
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .area-box-actions {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-inline-start: auto;
  }
  .area-box-badges {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > .settings-row {
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-2) 0;
    padding-inline: 0;
    border-block-start: 1px solid var(--studio-divider);
  }
  .area-presence-box > details.sub-collapsible {
    padding-block-start: var(--studio-space-2);
  }
  .area-presence-box > details.sub-collapsible > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > details.sub-collapsible[open] > summary,
  .area-presence-box > details.sub-collapsible > summary:hover {
    color: var(--studio-text);
  }
  .subsection-title {
    padding-block-start: var(--studio-space-3);
    border-block-start: 1px solid var(--studio-divider);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }
  .card-content > .subsection-title:first-child { padding-block-start: 0; border-block-start: none; }
`;
