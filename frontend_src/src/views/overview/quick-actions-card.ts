/**
 * Device Overview — Quick Actions Card (`views/overview/quick-actions-card.ts`, `D-066`, `M-P1-22`).
 */

import {
  renderCard,
  renderDeviceEntityRow,
  renderPrefControlRow,
  renderQuickActionGrid,
  renderSettingsRow,
} from "../../components/controls.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { EspHomeEntityItem } from "../../types.js";
import { entityLabel } from "../../utils/format.js";

function canonicalActionCommand(item: EspHomeEntityItem): string {
  if (item.device_command) return item.device_command;
  if (item.device_class === "identify") return "find_my";
  if (item.device_class === "restart") return "restart";
  const tail = (item.key || item.entity_id.split(".", 2)[1] || "").toLowerCase();
  if (tail === "find_my" || tail.endsWith("_find_my_device") || tail.endsWith("_find_my")) {
    return "find_my";
  }
  if (
    tail === "trigger_va" ||
    tail.endsWith("_trigger_voice_assistant") ||
    tail.endsWith("_trigger_va")
  ) {
    return "trigger_va";
  }
  if (tail === "activate_screensaver" || tail.endsWith("_activate_screensaver")) {
    return "activate_screensaver";
  }
  if (tail === "deactivate_screensaver" || tail.endsWith("_deactivate_screensaver")) {
    return "deactivate_screensaver";
  }
  if (tail === "hibernate" || tail.endsWith("_hibernate_device") || tail.endsWith("_hibernate")) {
    return "hibernate";
  }
  if (tail === "restart" || tail.endsWith("_restart_device") || tail.endsWith("_restart")) {
    return "restart";
  }
  return "";
}

function localizedQuickActionLabel(store: StudioStore, cmd: string, fallback: string): string {
  switch (cmd) {
    case "find_my":
      return store.t("dev_overview.qa_find_my");
    case "trigger_va":
      return store.t("dev_overview.qa_trigger_va");
    case "activate_screensaver":
      return store.t("dev_overview.qa_activate_screensaver");
    case "deactivate_screensaver":
      return store.t("dev_overview.qa_exit_screensaver");
    case "restart":
      return store.t("dev_overview.qa_restart");
    default:
      return entityLabel(fallback);
  }
}

export function renderOverviewQuickActionsCard(
  store: StudioStore,
  opts: {
    isBleOnly: boolean;
    isOffline: boolean;
    hasOpenInHa: boolean;
  },
): TemplateResult | typeof nothing {
  const { isBleOnly, isOffline, hasOpenInHa } = opts;
  if (isBleOnly) return nothing;
  const data = store.state;

  const sectionActionItems = store.entity
    .getSectionItems("actions")
    .concat(store.entity.getSectionItems("overview"));
  const sectionButtons = sectionActionItems.filter((it) => it.domain === "button");
  const synthesizedButtons: EspHomeEntityItem[] = (data?.quick_actions || []).map((qa) => {
    const cmd = qa.device_command || qa.key;
    return {
      entity_id: `cmd:${qa.key}`,
      domain: "button",
      name: localizedQuickActionLabel(store, cmd, qa.label),
      state: qa.state,
      key: qa.key,
      device_command: qa.device_command,
      device_class:
        qa.device_class ||
        (cmd === "find_my" ? "identify" : cmd === "restart" ? "restart" : undefined),
    };
  });
  const synthesizedCmdSet = new Set(
    synthesizedButtons.map((sb) => canonicalActionCommand(sb)).filter(Boolean),
  );
  const extraSectionButtons = sectionButtons.filter((b) => {
    const cmd = canonicalActionCommand(b);
    return !cmd || !synthesizedCmdSet.has(cmd);
  });
  const allQuickActionButtons = synthesizedButtons.concat(extraSectionButtons);
  const harmlessQuickButtons = allQuickActionButtons.filter(
    (b) => canonicalActionCommand(b) !== "restart",
  );
  const restartButton =
    allQuickActionButtons.find((b) => canonicalActionCommand(b) === "restart") || null;

  const otherQuickItemsRaw = sectionActionItems.filter((it) => it.domain !== "button");
  if (
    data?.speaker_volume &&
    !otherQuickItemsRaw.some((it) => it.entity_id === data.speaker_volume?.entity_id)
  ) {
    otherQuickItemsRaw.push(data.speaker_volume);
  }
  const dndPref = store.entity.getPref("do_not_disturb");
  const otherQuickItems = isOffline
    ? otherQuickItemsRaw.map((it) => ({ ...it, state: "unavailable" }))
    : otherQuickItemsRaw;
  const hasQuickControls =
    harmlessQuickButtons.length > 0 ||
    Boolean(dndPref) ||
    otherQuickItems.length > 0 ||
    Boolean(restartButton);

  const onTriggerRestart = (): void => {
    if (!restartButton) return;
    const toastMsg = store.t("sync.restarting_device");
    if (restartButton.device_command) {
      void store.entity.runDeviceAction(restartButton.device_command, toastMsg);
    } else {
      void store.entity.espAction(restartButton.entity_id, "press", undefined, toastMsg);
    }
  };

  return renderCard({
    id: "card-device-quick-actions",
    title: store.t("card.quick_actions"),
    contentClass: "settings-list",
    body: hasQuickControls
      ? html`${renderQuickActionGrid(store, harmlessQuickButtons, isOffline)}
          ${dndPref ? renderPrefControlRow(store, dndPref) : nothing}
          ${otherQuickItems.map((it) => renderDeviceEntityRow(store, it))}
          ${restartButton
            ? renderSettingsRow({
                id: "row-restart-device",
                label: store.t("dev_overview.restart_device"),
                description: store.t("dev_overview.restart_device_desc"),
                control: html`<button
                  type="button"
                  id="btn-restart-device"
                  data-entity-id=${restartButton.entity_id}
                  ?disabled=${isOffline || String(restartButton.state ?? "") === "unavailable"}
                  @click=${onTriggerRestart}
                  class="btn btn-danger btn-compact"
                >
                  ${store.t("dev_overview.restart_btn")}
                </button>`,
              })
            : nothing}`
      : html`<p class="empty-state">${store.t("dev_overview.empty_quick_actions")}</p>`,
    footerActions: hasOpenInHa
      ? html`<button
          type="button"
          id="btn-open-in-ha"
          @click=${() => store.openDeviceInHa()}
          class="btn btn-text"
        >
          ${store.t("action.open_in_ha")}
        </button>`
      : nothing,
  });
}
