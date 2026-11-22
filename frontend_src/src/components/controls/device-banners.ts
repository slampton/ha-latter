/**
 * Shared Device Offline Banner & Home Assistant Entity Row Renderer (`components/controls/device-banners.ts`, `M-P2-31`).
 *
 * Extracted from `views/device-overview-view.ts` so all `views/device-*-view.ts` modules
 * import strictly downward from `components/controls/*` with zero horizontal view-to-view edges.
 */

import { formatHaEntityState, type StudioTranslationKey } from "../../i18n/index.js";
import { html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { EspHomeEntityItem } from "../../types.js";
import { entityLabel, fmtNumber } from "../../utils/format.js";
import { renderNativeControlRow } from "./entity-adapters.js";
import { renderSettingsRow } from "./rows.js";

/**
 * Shared calm offline / sleeping banner rendered at the top of Device views (`Q8` / `E-04`).
 */
export function renderDeviceOfflineBanner(store: StudioStore): TemplateResult | typeof nothing {
  const data = store.state;
  const cfg = data?.config || {};
  if (cfg.kind === "ble_tag") return nothing;
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  if (curDevEntry?.is_online !== false) return nothing;
  const sleepExpected = Boolean(data?.live?.is_ble_sleep_expected);
  const titleKey: StudioTranslationKey = sleepExpected
    ? "offline.device_sleeping_title"
    : "offline.device_banner_title";
  return html`<div
    id="device-offline-banner"
    role="region"
    aria-label=${store.t(titleKey)}
    class="alert offline-banner"
  >
    <div class="offline-banner-body">
      <strong>${store.t(titleKey)}</strong>
      <span>${store.t("offline.device_banner_body")}</span>
    </div>
    <span class="chip">
      ${sleepExpected ? store.t("status.sleeping") : store.t("status.offline")}
    </span>
  </div>`;
}

/**
 * Formats non-pref Home Assistant entity `select` options and sensor states via `formatHaEntityState` (`D-13`),
 * while delegating preference-backed, switch, number, button, and update controls to `renderNativeControlRow`.
 */
export function renderDeviceEntityRow(
  store: StudioStore,
  item: EspHomeEntityItem,
): TemplateResult {
  if (
    item.pref_key ||
    item.domain === "switch" ||
    item.domain === "number" ||
    item.domain === "button" ||
    item.domain === "update"
  ) {
    return renderNativeControlRow(store, item);
  }

  const label = entityLabel(item.name || item.entity_id);
  const st = String(item.state ?? "");
  const unavailable = st === "unavailable" || st === "unknown";

  if (item.domain === "select") {
    const opts = item.options || [];
    const onChange = (ev: Event): void => {
      void store.entity.espSelect(item.entity_id, (ev.currentTarget as HTMLSelectElement).value);
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${live(st)} @change=${onChange}>
        ${opts.map(
          (opt) =>
            html`<option value=${opt} .selected=${live(opt === st)}>
              ${formatHaEntityState(store.hass, item.entity_id, opt)}
            </option>`,
        )}
      </select>`,
    });
  }

  const displayVal = unavailable
    ? store.t("common.unknown")
    : item.unit && Number.isFinite(Number(st))
      ? `${fmtNumber(Number(st), store.hass)} ${item.unit}`
      : formatHaEntityState(store.hass, item.entity_id, st);

  return html`<div class="kv-row">
    <span>${label}</span>
    <strong>${displayVal}</strong>
  </div>`;
}
