/**
 * Active-View-Only Router (`D-023`, `D-026`, `E-14`):
 * Renders ONLY the currently active Studio view and gates Device routes via `store.deviceHasView`.
 */

import type { TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { renderDeviceAudioView } from "./device-audio-view.js";
import { renderDeviceDisplayView } from "./device-display-view.js";
import { renderDeviceInterfaceView } from "./device-interface-view.js";
import { renderDeviceOverviewView } from "./device-overview-view.js";
import { renderDevicePowerView } from "./device-power-view.js";
import { renderDevicePresenceView } from "./device-presence-view.js";
import { renderDeviceToolsView } from "./device-tools-view.js";
import { renderDevicesDiscoveredView } from "./devices-discovered-view.js";
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

  const viewId = store.currentViewId;
  if (viewId === "discovered_devices") {
    return renderDevicesDiscoveredView(store);
  }

  if (!store.deviceSelected || viewId === "select_device_prompt") {
    return renderDevicesListView(store);
  }

  switch (viewId) {
    case "display":
      return store.deviceHasView("display")
        ? renderDeviceDisplayView(store)
        : renderDeviceOverviewView(store);
    case "interface":
      return store.deviceHasView("interface")
        ? renderDeviceInterfaceView(store)
        : renderDeviceOverviewView(store);
    case "audio_voice":
      return store.deviceHasView("audio_voice")
        ? renderDeviceAudioView(store)
        : renderDeviceOverviewView(store);
    case "power":
      return store.deviceHasView("power")
        ? renderDevicePowerView(store)
        : renderDeviceOverviewView(store);
    case "presence":
      return store.deviceHasView("presence")
        ? renderDevicePresenceView(store)
        : renderDeviceOverviewView(store);
    case "tools":
      return store.deviceHasView("tools")
        ? renderDeviceToolsView(store)
        : renderDeviceOverviewView(store);
    case "dashboard":
    default:
      return renderDeviceOverviewView(store);
  }
}
