/**
 * Active-View-Only Router (`D-023`): Renders ONLY the currently active Studio view.
 */

import type { TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { renderDeviceAudioView } from "./device-audio-view.js";
import { renderDeviceDisplayView } from "./device-display-view.js";
import { renderDeviceOverviewView } from "./device-overview-view.js";
import { renderDevicePowerView } from "./device-power-view.js";
import { renderDevicePresenceView } from "./device-presence-view.js";
import { renderDeviceToolsView } from "./device-tools-view.js";
import { renderDevicesListView } from "./devices-list-view.js";
import { renderSystemGroupsView } from "./system-groups-view.js";
import { renderSystemOverviewView } from "./system-overview-view.js";
import { renderSystemPresenceView } from "./system-presence-view.js";
import { renderSystemRemotesView } from "./system-remotes-view.js";
import { renderSystemSharedView } from "./system-shared-view.js";
import { renderSystemToolsView } from "./system-tools-view.js";

export function renderActiveView(store: StudioStore): TemplateResult {
  if (store.currentScope === "system") {
    switch (store.currentViewId) {
      case "shared_entities":
        return renderSystemSharedView(store);
      case "remotes":
        return renderSystemRemotesView(store);
      case "system_sync":
        return renderSystemGroupsView(store);
      case "area_tracking":
        return renderSystemPresenceView(store);
      case "system_tools":
        return renderSystemToolsView(store);
      case "system_overview":
      default:
        return renderSystemOverviewView(store);
    }
  }

  if (!store.deviceSelected || store.currentViewId === "select_device_prompt") {
    return renderDevicesListView(store);
  }

  switch (store.currentViewId) {
    case "home_display":
      return renderDeviceDisplayView(store);
    case "audio_voice":
      return renderDeviceAudioView(store);
    case "power":
      return renderDevicePowerView(store);
    case "presence":
      return renderDevicePresenceView(store);
    case "tools":
      return renderDeviceToolsView(store);
    case "dashboard":
    default:
      return renderDeviceOverviewView(store);
  }
}
