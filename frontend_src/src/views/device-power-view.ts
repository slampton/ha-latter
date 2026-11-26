/**
 * Device Power View (`power`, `D-014`, `D-027`, `D-036`, `D-066`, `D-068`):
 * Sleep & wake settings and Bedtime mode configuration (battery telemetry lives under Device → Tools).
 */

import {
  renderCard,
  renderDeviceOfflineBanner,
  renderPrefControlRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderDevicePowerView(store: StudioStore): TemplateResult {
  const sleepPrefs = store.entity.getPrefs([
    "tap_to_wake",
    "pickup_to_wake",
    "battery_screen_timeout",
    "battery_hibernate_timeout",
  ]);

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

  const sleepItems = sleepPrefs;
  const allEmpty = !sleepItems.length && !bedtimePrefs.length;

  return html`<section id="view-power">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${sleepItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h2 class="card-title">${store.t("dev_power.card_sleep_wake")}</h2>
              </div>
              <div class="card-content settings-list">
                ${sleepPrefs.map((p) => renderPrefControlRow(store, p))}
              </div>
            </div>`
          : allEmpty
            ? renderCard({
                title: store.t("view.power"),
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
      </div>
    </div>
  </section>`;
}
