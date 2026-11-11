/**
 * Device Power & Battery View (`power`): Sleep & Wake controls and Power & Battery telemetry (D-014).
 */

import { renderNativeControlRow } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderDevicePowerView(store: StudioStore): TemplateResult {
  const sleepItems = store.getSectionItems("sleep");
  const batteryItems = store.getSectionItems("battery");
  const bothEmpty = !sleepItems.length && !batteryItems.length;

  return html`<section id="view-power">
    <div class="columns">
      <div class="column">
        ${sleepItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Sleep &amp; Wake</h3>
              </div>
              <div class="card-content settings-list">
                ${sleepItems.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : bothEmpty
            ? html`<div class="card">
                <div class="card-header">
                  <h3 class="card-title">Power &amp; Battery</h3>
                </div>
                <div class="card-content">
                  <p class="empty-state">No sleep or battery entities reported by this Device.</p>
                </div>
              </div>`
            : nothing}
      </div>
      <div class="column">
        ${batteryItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Power &amp; Battery</h3>
              </div>
              <div class="card-content settings-list">
                ${batteryItems.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : nothing}
      </div>
    </div>
  </section>`;
}
