/**
 * Group Baseline Drawer (`system_sync` Column 1, `D-048`, `D-050`, `D-063`, `D-064`).
 *
 * Composes `baseline-{behavior,display,interface}-section.ts` with trait-gated
 * spec adapters (`isCatalogItemSupported`) and confirmation-guarded copy-from-Device actions.
 */

import {
  renderHourSelectRow,
  renderRangeRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../../components/controls.js";
import type { CatalogItem } from "../../constants.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import { isCatalogItemSupported, type StudioStore } from "../../state/store.js";
import type {
  DeviceCapabilities,
  DeviceGroup,
  SystemDeviceEntry,
} from "../../types.js";
import { defaultLocaleTimeFormat } from "../../utils/format.js";
import { renderBaselineBehaviorSection } from "./baseline-behavior-section.js";
import { renderBaselineDisplaySection } from "./baseline-display-section.js";
import { renderBaselineInterfaceSection } from "./baseline-interface-section.js";

function deriveGroupCapabilities(
  group: DeviceGroup,
  members: readonly SystemDeviceEntry[],
): DeviceCapabilities {
  if (group.id === "pocket_carry") {
    return {
      has_display: true,
      is_round: true,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: false,
    };
  }
  if (group.id === "handhelds") {
    return {
      has_display: true,
      is_round: false,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: members.length > 0 ? members.some((m) => m.hw_jpeg === true) : true,
    };
  }
  if (group.id === "wearables") {
    return {
      has_display: true,
      is_round: false,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: false,
    };
  }
  if (group.id === "wall_panels") {
    return {
      has_display: true,
      is_round: false,
      has_imu: false,
      has_battery: false,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: false,
      hw_jpeg: true,
    };
  }
  if (members.length > 0) {
    return {
      has_display: members.some((m) => m.has_display !== false),
      has_battery: members.some((m) => m.has_battery !== false),
      has_ble_beacon: members.some((m) => m.has_ble !== false),
      is_roaming_device: members.some((m) => m.is_roaming !== false),
      hw_jpeg: members.some((m) => m.hw_jpeg === true),
    };
  }
  return { hw_jpeg: true };
}

function renderSpecSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (!spec || !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const options = spec.options || [];
  if (options.length === 0) return nothing;
  const fallbackVal = String(spec.default ?? options[0]);
  const cur =
    typeof currentVal === "string" && options.includes(currentVal) ? currentVal : fallbackVal;
  const label = store.tPrefLabel(key, spec.label);
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      .value=${cur}
      @change=${(ev: Event) =>
        void store.groups.updateGroupBaseline(group.id, {
          [key]: (ev.currentTarget as HTMLSelectElement).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} ?selected=${opt === cur}>
          ${store.tPrefOption(key, opt)}
        </option>`,
      )}
    </select>`,
  });
}

function renderSpecSwitch(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
  extraGate = true,
): TemplateResult | typeof nothing {
  if (!extraGate) return nothing;
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const defaultBool = spec ? Boolean(spec.default) : true;
  const checked =
    currentVal !== undefined && currentVal !== null ? Boolean(currentVal) : defaultBool;
  const label = store.tPrefLabel(key, spec?.label);
  return renderSwitchRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    checked,
    onChange: (next) => void store.groups.updateGroupBaseline(group.id, { [key]: next }),
  });
}

function renderSpecRange(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
  fallbackBounds?: { min: number; max: number; step: number; unit: string; defaultVal: number },
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const min = spec?.min ?? fallbackBounds?.min ?? 0;
  const max = spec?.max ?? fallbackBounds?.max ?? 100;
  const step = spec?.step ?? fallbackBounds?.step ?? 1;
  const unit = spec?.unit ?? fallbackBounds?.unit ?? "";
  const defNum = Number(spec?.default ?? fallbackBounds?.defaultVal ?? min);
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defNum;
  const label = store.tPrefLabel(key, spec?.label);

  return renderRangeRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    value: numVal,
    min,
    max,
    step,
    unit,
    is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
    hass: store.hass,
    onCommit: (nextVal) =>
      void store.groups.updateGroupBaseline(group.id, { [key]: nextVal }),
  });
}

function renderSpecHourSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const defNum = Number(spec?.default ?? 0);
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defNum;
  const label = store.tPrefLabel(key, spec?.label);

  return renderHourSelectRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    value: numVal,
    is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
    hass: store.hass,
    onCommit: (nextHour) =>
      void store.groups.updateGroupBaseline(group.id, { [key]: nextHour }),
  });
}

function renderBaselineLabeledSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  options: ReadonlyArray<{ value: string; label: string }>,
  defaultVal: string,
  asNumber = false,
): TemplateResult {
  const curStr =
    currentVal !== undefined && currentVal !== null ? String(currentVal) : defaultVal;
  const cur = options.some((o) => o.value === curStr) ? curStr : defaultVal;
  const label = store.tPrefLabel(key);
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      .value=${cur}
      @change=${(ev: Event) => {
        const raw = (ev.currentTarget as HTMLSelectElement).value;
        const val = asNumber ? Number(raw) || 0 : raw;
        void store.groups.updateGroupBaseline(group.id, { [key]: val });
      }}
    >
      ${options.map(
        (opt) =>
          html`<option value=${opt.value} ?selected=${opt.value === cur}>
            ${opt.label}
          </option>`,
      )}
    </select>`,
  });
}

function renderBaselinePills(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  catalog: ReadonlyArray<CatalogItem>,
  defaultCsv: string,
  minRequired: number,
  caps: DeviceCapabilities,
): TemplateResult {
  const supportedCatalog = catalog.filter((c) => isCatalogItemSupported(c, caps));
  const csvStr = typeof currentVal === "string" ? currentVal : defaultCsv;
  const activeSet = new Set(
    csvStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  const label = store.tPrefLabel(key);

  const toggleTok = (tok: string): void => {
    const next = new Set(activeSet);
    if (next.has(tok)) {
      if (next.size <= minRequired) {
        const noun =
          key === "tools_items"
            ? "tool"
            : key === "games_items"
              ? "game"
              : "category";
        store.showToast(store.t("common.keep_one_enabled", { noun }), true);
        return;
      }
      next.delete(tok);
    } else {
      next.add(tok);
    }
    const ordered = catalog.map((c) => c.token).filter((t) => next.has(t));
    void store.groups.updateGroupBaseline(group.id, { [key]: ordered.join(",") });
  };

  return renderSettingsRow({
    label,
    stacked: true,
    control: html`<div
      role="group"
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      class="pill-list"
    >
      ${supportedCatalog.map((item) => {
        const on = activeSet.has(item.token);
        return html`<span class="pill ${on ? "enabled" : ""}">
          <button
            type="button"
            aria-pressed=${on ? "true" : "false"}
            @click=${() => toggleTok(item.token)}
            class="pill-toggle"
          >
            ${item.label}
          </button>
        </span>`;
      })}
    </div>`,
  });
}

function requestCopyDeviceIntoGroup(
  store: StudioStore,
  group: DeviceGroup,
  memberCount: number,
  sourceSubentryId: string,
  latterDevices: readonly SystemDeviceEntry[],
  copyKeys?: string[],
  listLabel?: string,
): void {
  const srcDev = latterDevices.find((d) => d.subentry_id === sourceSubentryId);
  const devName = srcDev?.title || sourceSubentryId;
  store.openConfirm({
    kind: "copy_group_baseline",
    title: store.t("groups.confirm_copy_title", { group: group.name }),
    consequence: listLabel
      ? store.t("groups.confirm_copy_list_body", {
          listLabel,
          device: devName,
          group: group.name,
        })
      : store.t("groups.confirm_copy_body", {
          group: group.name,
          device: devName,
        }),
    confirmLabel: store.t("groups.confirm_copy_confirm"),
    danger: false,
    blastRadiusCount: memberCount > 0 ? memberCount : null,
    onConfirm: async () => {
      await store.groups.copyDeviceToGroupBaseline(group.id, sourceSubentryId, copyKeys);
    },
  });
}

export function renderGroupBaselineDrawer(
  store: StudioStore,
  group: DeviceGroup,
  members: readonly SystemDeviceEntry[],
  latterDevices: readonly SystemDeviceEntry[],
): TemplateResult {
  const gid = group.id;
  const caps = deriveGroupCapabilities(group, members);
  const includeDisplay = Boolean(group.include_display);
  const includeInterface = Boolean(group.include_interface);
  const copySrc =
    store.groupCopySourceDrafts.get(gid) ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";

  const helpers = {
    caps,
    hasLatterDevices: latterDevices.length > 0,
    renderSpecSelect: (key: string, currentVal: unknown) =>
      renderSpecSelect(store, group, key, currentVal, caps),
    renderSpecSwitch: (key: string, currentVal: unknown, extraGate = true) =>
      renderSpecSwitch(store, group, key, currentVal, caps, extraGate),
    renderSpecRange: (
      key: string,
      currentVal: unknown,
      fallbackBounds?: { min: number; max: number; step: number; unit: string; defaultVal: number },
    ) => renderSpecRange(store, group, key, currentVal, caps, fallbackBounds),
    renderSpecHourSelect: (key: string, currentVal: unknown) =>
      renderSpecHourSelect(store, group, key, currentVal, caps),
    renderLabeledSelect: (
      key: string,
      currentVal: unknown,
      options: ReadonlyArray<{ value: string; label: string }>,
      defaultVal: string,
      asNumber = false,
    ) =>
      renderBaselineLabeledSelect(store, group, key, currentVal, options, defaultVal, asNumber),
    renderPills: (
      key: string,
      currentVal: unknown,
      catalog: ReadonlyArray<CatalogItem>,
      defaultCsv: string,
      minRequired: number,
    ) => renderBaselinePills(store, group, key, currentVal, catalog, defaultCsv, minRequired, caps),
    requestCopyKeys: (copyKeys: string[], listLabel: string) =>
      requestCopyDeviceIntoGroup(
        store,
        group,
        members.length,
        copySrc,
        latterDevices,
        copyKeys,
        listLabel,
      ),
  };

  return html`<details
    ?open=${store.openGroupIds.has(gid)}
    @toggle=${(ev: Event) => {
      if (ev.target !== ev.currentTarget) return;
      const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
      if (isOpen) store.openGroupIds.add(gid);
      else store.openGroupIds.delete(gid);
    }}
    class="sub-collapsible"
  >
    <summary>${store.t("groups.baseline_settings")}</summary>
    <div class="card-content stack">
      <div class="settings-list">
        ${renderSwitchRow({
          label: store.t("groups.include_display"),
          description: store.t("groups.include_display_desc"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.t("groups.include_display"),
            group: group.name,
          }),
          checked: includeDisplay,
          onChange: (checked) =>
            void store.groups.updateGroupScope(gid, { include_display: checked }),
        })}
        ${renderSwitchRow({
          label: store.t("groups.include_interface"),
          description: store.t("groups.include_interface_desc"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.t("groups.include_interface"),
            group: group.name,
          }),
          checked: includeInterface,
          onChange: (checked) =>
            void store.groups.updateGroupScope(gid, { include_interface: checked }),
        })}
      </div>

      ${renderBaselineBehaviorSection(store, group, helpers)}
      ${renderBaselineDisplaySection(store, group, helpers)}
      ${renderBaselineInterfaceSection(store, group, helpers)}

      ${latterDevices.length
        ? html`<div class="settings-list">
            <div class="subsection-title">${store.t("groups.copy_from_device")}</div>
            ${renderSettingsRow({
              label: store.t("groups.source_device"),
              description: store.t("groups.source_device_desc"),
              control: html`<select
                  aria-label=${store.t("groups.copy_into_aria", { name: group.name })}
                  .value=${copySrc}
                  @change=${(ev: Event) => {
                    store.groupCopySourceDrafts.set(
                      gid,
                      (ev.currentTarget as HTMLSelectElement).value,
                    );
                    store.host.requestUpdate();
                  }}
                >
                  ${latterDevices.map(
                    (d) =>
                      html`<option value=${d.subentry_id} ?selected=${d.subentry_id === copySrc}>
                        ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() =>
                    requestCopyDeviceIntoGroup(
                      store,
                      group,
                      members.length,
                      copySrc,
                      latterDevices,
                    )}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("groups.copy_settings")}
                </button>`,
            })}
          </div>`
        : nothing}
    </div>
  </details>`;
}
