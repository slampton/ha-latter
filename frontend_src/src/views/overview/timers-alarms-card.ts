/**
 * Device Overview — Timers & Alarms Card (`views/overview/timers-alarms-card.ts`, `F-01`, `B-17`, `M-P1-50`).
 */

import {
  isDeviceTime24h,
  renderCard,
  renderSettingsRow,
} from "../../components/controls.js";
import { DEFAULT_ALARMS_SUMMARY } from "../../constants.js";
import {
  type AlarmSlotView,
  formatClockDuration,
  parseAlarmsSummary,
  serializeAlarmsSummary,
} from "../../domain/alarms.js";
import { html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import { fmtNumber, formatClockHhMm } from "../../utils/format.js";

export function renderOverviewTimersAlarmsCard(
  store: StudioStore,
  opts: {
    isBleOnly: boolean;
    isOffline: boolean;
  },
): TemplateResult | typeof nothing {
  const { isBleOnly, isOffline } = opts;
  const data = store.state;
  const cfg = data?.config || {};
  const liveData = data?.live || {};
  const caps = data?.capabilities || {};

  if (isBleOnly || !caps.has_display) return nothing;

  const alarmsSummaryPref = store.entity.getPref("alarms_summary");
  const alarmSlots = parseAlarmsSummary(
    alarmsSummaryPref?.value ?? cfg.alarms_summary ?? DEFAULT_ALARMS_SUMMARY,
  );
  const updateAlarmSlot = (
    idx: 0 | 1 | 2,
    patch: Partial<AlarmSlotView>,
    focusId?: string,
  ): void => {
    const next: [AlarmSlotView, AlarmSlotView, AlarmSlotView] = [
      { ...alarmSlots[0] },
      { ...alarmSlots[1] },
      { ...alarmSlots[2] },
    ];
    const merged = { ...next[idx], ...patch };
    if (!/^\d{2}:\d{2}$/.test(merged.time)) {
      return;
    }
    next[idx] = merged;
    store.entity.stageDeviceSetting("alarms_summary", serializeAlarmsSummary(next), focusId);
  };

  const nowMs = Number.isFinite(store.liveClockNowMs) ? store.liveClockNowMs : Date.now();
  const timerEndsMs = liveData.timer_ends_at ? Date.parse(liveData.timer_ends_at) : Number.NaN;
  const liveTimerRemainingSec =
    liveData.timer_running && Number.isFinite(timerEndsMs)
      ? Math.max(0, Math.ceil((timerEndsMs - nowMs) / 1000))
      : Math.max(0, Math.round(Number(liveData.timer_remaining_sec || 0)));

  const stopwatchStartedMs = liveData.stopwatch_started_at
    ? Date.parse(liveData.stopwatch_started_at)
    : Number.NaN;
  const liveStopwatchElapsedSec =
    liveData.stopwatch_running && Number.isFinite(stopwatchStartedMs)
      ? Math.max(0, Math.floor((nowMs - stopwatchStartedMs) / 1000))
      : Math.max(0, Math.round(Number(liveData.stopwatch_elapsed_sec || 0)));

  const timerActive = Boolean(liveData.timer_running || liveData.timer_paused);
  const stopwatchActive = Boolean(liveData.stopwatch_running || liveData.stopwatch_paused);
  const alarmRinging = Boolean(liveData.alarm_ringing);
  const enabledAlarmSlots = alarmSlots
    .filter((s) => s.enabled)
    .sort((a, b) => a.time.localeCompare(b.time));
  const is24h = isDeviceTime24h(store);
  const nextEnabledSlot = enabledAlarmSlots[0];
  const alarmsSummaryLabel = nextEnabledSlot
    ? store.t("dev_overview.alarms_enabled_summary", {
        count: fmtNumber(enabledAlarmSlots.length, store.hass, 0),
        nextTime: formatClockHhMm(nextEnabledSlot.time, is24h),
      })
    : store.t("common.all_off");
  const alarmsSummaryChipClass = nextEnabledSlot ? "chip chip-primary" : "chip";

  const alarmRecurrenceChoices: ReadonlyArray<{ value: number; label: string }> = [
    { value: 0, label: store.t("dev_overview.alarm_rec_daily") },
    { value: 1, label: store.t("dev_overview.alarm_rec_weekdays") },
    { value: 2, label: store.t("dev_overview.alarm_rec_weekends") },
    { value: 3, label: store.t("dev_overview.alarm_rec_once") },
  ];

  return renderCard({
    id: "card-device-timers-alarms",
    title: store.t("card.timers_alarms"),
    body: html`${alarmRinging
        ? html`<div id="overview-ringing-alert" role="alert" class="alert alert-warning">
            <span>${store.t("dev_overview.ringing_alert_text")}</span>
            <button
              type="button"
              id="btn-dismiss-ringing"
              ?disabled=${isOffline}
              @click=${() =>
                void store.entity.runDeviceAction(
                  "dismiss_ringing",
                  store.t("dev_overview.dismissed_ringing_toast"),
                )}
              class="btn btn-secondary btn-compact"
            >
              ${store.t("action.dismiss")}
            </button>
          </div>`
        : nothing}
      <div class="settings-list">
        ${renderSettingsRow({
          id: "overview-active-timer",
          label: store.t("dev_overview.active_timer_label"),
          description: timerActive ? undefined : store.t("dev_overview.no_active_timer"),
          control: timerActive
            ? html`<span class="chip ${liveData.timer_running ? "chip-primary" : ""}">
                  ${liveData.timer_running
                    ? store.t("dev_overview.running")
                    : store.t("dev_overview.paused")}
                </span>
                <strong class="kv-value">
                  ${formatClockDuration(liveTimerRemainingSec)}
                </strong>
                <button
                  type="button"
                  id="btn-cancel-timer"
                  ?disabled=${isOffline}
                  @click=${() =>
                    void store.entity.runDeviceAction(
                      "cancel_timer",
                      store.t("dev_overview.cancelled_timer_toast"),
                    )}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("dev_overview.cancel_timer")}
                </button>`
            : html`<span class="kv-value">${store.t("common.unknown")}</span>`,
        })}
        ${renderSettingsRow({
          id: "overview-stopwatch",
          label: store.t("dev_overview.stopwatch_label"),
          description: stopwatchActive ? undefined : store.t("dev_overview.not_running"),
          control: stopwatchActive
            ? html`<span class="chip ${liveData.stopwatch_running ? "chip-primary" : ""}">
                  ${liveData.stopwatch_running
                    ? store.t("dev_overview.running")
                    : store.t("dev_overview.paused")}
                </span>
                <strong class="kv-value">
                  ${formatClockDuration(liveStopwatchElapsedSec)}
                </strong>
                <button
                  type="button"
                  id="btn-reset-stopwatch"
                  ?disabled=${isOffline}
                  @click=${() =>
                    void store.entity.runDeviceAction(
                      "reset_stopwatch",
                      store.t("dev_overview.reset_stopwatch_toast"),
                    )}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("dev_overview.reset_stopwatch")}
                </button>`
            : html`<span class="kv-value">${store.t("common.unknown")}</span>`,
        })}
        <details
          id="overview-alarms-drawer"
          class="sub-collapsible summary-row"
          ?open=${store.overviewAlarmsOpen}
          @toggle=${(ev: Event) => {
            store.overviewAlarmsOpen = (ev.currentTarget as HTMLDetailsElement).open;
          }}
        >
          <summary>
            <span class="row-label">${store.t("dev_overview.alarms_label")}</span>
            <span class="summary-row-end">
              <span id="overview-alarms-chip" class=${alarmsSummaryChipClass}>
                ${alarmsSummaryLabel}
              </span>
              <span class="summary-chevron" aria-hidden="true">▾</span>
            </span>
          </summary>
          <div id="overview-alarms" class="card-content stack">
            <p class="row-description">${store.t("dev_overview.alarms_desc")}</p>
            <div
              class="stack"
              role="group"
              aria-label=${store.t("dev_overview.alarms_group_aria")}
            >
              ${([0, 1, 2] as const).map((idx) => {
                const slot = alarmSlots[idx];
                const timeId = `cfg-alarm_${idx + 1}_time`;
                const recId = `cfg-alarm_${idx + 1}_recurrence`;
                const enId = `cfg-alarm_${idx + 1}_enabled`;
                return html`<div class="list-row">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for=${timeId}>
                        ${store.t("dev_overview.alarm_time_label", { index: idx + 1 })}
                      </label>
                      <input
                        type="time"
                        id=${timeId}
                        step="60"
                        .value=${live(slot.time)}
                        @change=${(ev: Event) => {
                          const val = (ev.currentTarget as HTMLInputElement).value;
                          if (val) {
                            updateAlarmSlot(idx, { time: val.slice(0, 5) }, timeId);
                          }
                        }}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for=${recId}>
                        ${store.t("dev_overview.alarm_schedule_label", { index: idx + 1 })}
                      </label>
                      <select
                        id=${recId}
                        .value=${live(String(slot.recurrence))}
                        @change=${(ev: Event) =>
                          updateAlarmSlot(
                            idx,
                            {
                              recurrence: Number(
                                (ev.currentTarget as HTMLSelectElement).value,
                              ),
                            },
                            recId,
                          )}
                      >
                        ${alarmRecurrenceChoices.map(
                          (opt) =>
                            html`<option
                              value=${String(opt.value)}
                              .selected=${live(opt.value === slot.recurrence)}
                            >
                              ${opt.label}
                            </option>`,
                        )}
                      </select>
                    </div>
                  </div>
                  <label for=${enId} class="inline-switch">
                    <span>${store.t("common.enabled")}</span>
                    <input
                      type="checkbox"
                      id=${enId}
                      .checked=${live(slot.enabled)}
                      @change=${(ev: Event) =>
                        updateAlarmSlot(
                          idx,
                          { enabled: (ev.currentTarget as HTMLInputElement).checked },
                          enId,
                        )}
                      role="switch"
                      class="switch"
                    />
                  </label>
                </div>`;
              })}
            </div>
          </div>
        </details>
      </div>`,
  });
}
