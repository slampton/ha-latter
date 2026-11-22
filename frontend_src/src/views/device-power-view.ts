/**
 * Device Power View (`power`, `D-014`, `D-027`, `D-036`, `D-066`, `D-068`):
 * Sleep & wake controls, Bedtime mode, and Power & battery telemetry.
 */

import {
  renderCard,
  renderDeviceEntityRow,
  renderDeviceOfflineBanner,
  renderPrefControlRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

const SCREENSAVER_KEYS = new Set([
  "screensaver_mode",
  "screensaver_style",
  "docked_idle_timeout",
  "screensaver_photo_clock",
]);

const BEDTIME_KEYS = new Set([
  "do_not_disturb",
  "bedtime_active",
  "bedtime_display",
  "bedtime_brightness",
  "bedtime_schedule",
  "bedtime_start_hour",
  "bedtime_end_hour",
  "bedtime_mode",
]);

export function renderDevicePowerView(store: StudioStore): TemplateResult {
  const sleepPrefs = store.entity
    .getPrefs([
      "tap_to_wake",
      "pickup_to_wake",
      "battery_screen_timeout",
      "battery_hibernate_timeout",
    ])
    .filter((p) => !SCREENSAVER_KEYS.has(p.key));

  const bedtimeAllPrefs = store.entity.getPrefs([
    "do_not_disturb",
    "bedtime_active",
    "bedtime_display",
    "bedtime_brightness",
    "bedtime_schedule",
    "bedtime_start_hour",
    "bedtime_end_hour",
  ]);
  const bedtimeScheduleOn = Boolean(
    bedtimeAllPrefs.find((p) => p.key === "bedtime_schedule")?.value,
  );
  const bedtimePrefs = bedtimeAllPrefs.filter(
    (p) =>
      bedtimeScheduleOn ||
      (p.key !== "bedtime_start_hour" && p.key !== "bedtime_end_hour"),
  );

  const sleepPrefKeys = new Set(sleepPrefs.map((p) => p.key));
  const sleepEntities = store.entity.getSectionItems("sleep").filter((it) => {
    if (it.pref_key) return false;
    const k = it.key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (SCREENSAVER_KEYS.has(k) || Array.from(SCREENSAVER_KEYS).some((sk) => k.endsWith(sk))) {
      return false;
    }
    if (BEDTIME_KEYS.has(k) || Array.from(BEDTIME_KEYS).some((bk) => k.endsWith(bk))) {
      return false;
    }
    if (sleepPrefKeys.has(k) || Array.from(sleepPrefKeys).some((pk) => k.endsWith(pk))) {
      return false;
    }
    return true;
  });

  const batteryItems = store.entity.getSectionItems("battery");
  const sleepItems = [...sleepPrefs, ...sleepEntities];
  const allEmpty = !sleepItems.length && !bedtimePrefs.length && !batteryItems.length;

  return html`<section id="view-power">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${sleepItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">${store.t("dev_power.card_sleep_wake")}</h3>
              </div>
              <div class="card-content settings-list">
                ${sleepPrefs.map((p) => renderPrefControlRow(store, p))}
                ${sleepEntities.map((it) => renderDeviceEntityRow(store, it))}
              </div>
            </div>`
          : allEmpty
            ? renderCard({
                title: store.t("dev_power.card_power_battery"),
                body: html`<p class="empty-state">${store.t("dev_power.empty")}</p>`,
              })
            : nothing}
      </div>
      <div class="column">
        ${bedtimePrefs.length
          ? renderCard({
              id: "card-bedtime-mode",
              title: store.t("dev_power.card_bedtime"),
              subtitle: store.t("dev_power.card_bedtime_subtitle"),
              contentClass: "settings-list",
              body: html`${bedtimePrefs.map((p) => renderPrefControlRow(store, p))}`,
            })
          : nothing}
        ${batteryItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">${store.t("dev_power.card_power_battery")}</h3>
              </div>
              <div class="card-content settings-list">
                ${batteryItems.map((it) => renderDeviceEntityRow(store, it))}
              </div>
            </div>`
          : nothing}
      </div>
    </div>
  </section>`;
}
