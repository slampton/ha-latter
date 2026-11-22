/**
 * Device Overview View (`dashboard`, `D-003`, `D-014`, `D-029`, `D-030`, `D-048`, `D-066`).
 *
 * Composes `views/overview/{status-card,quick-actions-card,assignments-card,timers-alarms-card}.ts`
 * inside the canonical two-column `.columns > .column` layout (`D-014`).
 */

import {
  renderCard,
  renderDeviceEntityRow,
  renderDeviceOfflineBanner,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { issueMessage } from "../utils/format.js";
import { renderOverviewAssignmentsCard } from "./overview/assignments-card.js";
import { renderOverviewQuickActionsCard } from "./overview/quick-actions-card.js";
import { renderOverviewStatusCard } from "./overview/status-card.js";
import { renderOverviewTimersAlarmsCard } from "./overview/timers-alarms-card.js";

export function renderDeviceOverviewView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const links = data?.links || {};
  const isBleOnly = cfg.kind === "ble_tag";

  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const isOffline = !isBleOnly && curDevEntry?.is_online === false;
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);

  const deviceIssues = (data?.issues || []).filter(
    (i) => i.subentry_id && i.subentry_id === store.activeSubentryId,
  );
  const hasErrorIssue = deviceIssues.some(
    (i) => i.severity === "error" || i.severity === "critical",
  );

  const txStatus = isBleOnly ? live.ble_transmitter_status : null;
  const txStateText = String(txStatus?.state || "").trim();
  const showTxOffBanner =
    Boolean(txStatus) && Boolean(txStateText) && txStateText.toLowerCase() !== "transmitting";

  const hasOpenInHa = Boolean(links.esphome_device_id || links.latter_device_id);
  const otherSensorItems = store.entity.getSectionItems("other");

  return html`<section id="view-dashboard" class="stack">
    ${renderDeviceOfflineBanner(store)}

    ${deviceIssues.length
      ? html`<div
          role="region"
          aria-label=${store.t("status.needs_attention")}
          class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}"
        >
          <div class="alert-body">
            <strong>${store.t("status.needs_attention")}</strong>
            <ul class="alert-list">
              ${deviceIssues.map((iss) => html`<li>${issueMessage(iss, store.hass)}</li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("action.open_repairs")}
          </button>
        </div>`
      : nothing}

    ${showTxOffBanner
      ? html`<div
          id="ble-transmitter-off-banner"
          role="region"
          aria-label=${store.t("offline.ble_tx_off_title", { state: txStateText })}
          class="alert alert-warning"
        >
          <div class="alert-body">
            <strong>${store.t("offline.ble_tx_off_title", { state: txStateText })}</strong>
            <span>${store.t("offline.ble_tx_off_body")}</span>
          </div>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderOverviewStatusCard(store, {
          curDevEntry,
          winRow,
          isBleOnly,
          hasOpenInHa,
        })}
        ${renderOverviewQuickActionsCard(store, {
          isBleOnly,
          isOffline,
          hasOpenInHa,
        })}
      </div>

      <div class="column">
        ${renderOverviewAssignmentsCard(store, {
          curDevEntry,
          isBleOnly,
        })}
        ${renderOverviewTimersAlarmsCard(store, {
          isBleOnly,
          isOffline,
        })}
        ${otherSensorItems.length
          ? renderCard({
              title: store.t("card.sensors_controls"),
              contentClass: "settings-list",
              body: otherSensorItems.map((it) => renderDeviceEntityRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
