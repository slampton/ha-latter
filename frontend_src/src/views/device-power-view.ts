/**
 * Device Power View (`power`, D-014 / D-027 / D-036): Sleep & Wake controls and Power & Battery telemetry.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderPrefControlRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

const SCREENSAVER_KEYS = new Set([
  "docked_screensaver",
  "screensaver_style",
  "docked_idle_timeout",
]);

export function renderDevicePowerView(store: StudioStore): TemplateResult {
  const sleepPrefs = store
    .getPrefs([
      "power_profile",
      "tap_to_wake",
      "pickup_to_wake",
      "battery_screen_timeout",
      "battery_hibernate_timeout",
      "hold_crown_power_off",
    ])
    .filter((p) => !SCREENSAVER_KEYS.has(p.key));

  const sleepPrefKeys = new Set(sleepPrefs.map((p) => p.key));
  const sleepEntities = store.getSectionItems("sleep").filter((it) => {
    if (it.pref_key) return false;
    const k = it.key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (SCREENSAVER_KEYS.has(k) || Array.from(SCREENSAVER_KEYS).some((sk) => k.endsWith(sk))) {
      return false;
    }
    if (sleepPrefKeys.has(k) || Array.from(sleepPrefKeys).some((pk) => k.endsWith(pk))) {
      return false;
    }
    return true;
  });

  const batteryItems = store.getSectionItems("battery");
  const sleepItems = [...sleepPrefs, ...sleepEntities];
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
                ${sleepPrefs.map((p) => renderPrefControlRow(store, p))}
                ${sleepEntities.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : bothEmpty
            ? renderCard({
                title: "Power & Battery",
                body: html`<p class="empty-state">
                  No sleep or battery entities reported by this Device.
                </p>`,
              })
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
