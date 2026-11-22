/**
 * Walk-Around BLE Calibration, Scanner Antenna Trim, Area Sensor Fusion,
 * & Area Illuminance Calibration Operations (`D-064`, `D-075`).
 */

import { formatWsError } from "../api/ws-client.js";
import type { SystemDeviceEntry } from "../types.js";
import type { StudioStoreContext } from "./store-types.js";

export interface IlluminanceCalibrationState {
  calibratingAllIlluminance: boolean;
  readonly calibratingIlluminanceAreas: Set<string>;
}

export function isCalibratingIlluminanceOp(
  calState: IlluminanceCalibrationState,
  areaId?: string,
): boolean {
  if (calState.calibratingAllIlluminance) return true;
  return Boolean(areaId && calState.calibratingIlluminanceAreas.has(String(areaId)));
}

export function selectBleSurveyDeviceOp(store: StudioStoreContext, subentryId: string): void {
  store.bleSurveySubentryId = subentryId;
  store.host.requestUpdate();
  void store.ensureSubscription(false);
}

export function selectBleCalibrateAreaOp(
  store: StudioStoreContext,
  areaId: string,
  fromAreaCard = false,
): void {
  store.bleCalibrateAreaId = String(areaId || "");
  if (fromAreaCard) {
    store.handoffTargetIds.clear();
    store.bleCalibrateHandoffActive = true;
  }
  store.host.requestUpdate();
  if (fromAreaCard && typeof globalThis.requestAnimationFrame === "function") {
    globalThis.requestAnimationFrame(() => {
      const root =
        (store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
        store.host.shadowRoot;
      const cardEl =
        root?.getElementById("card-ble-calibration") ||
        root?.getElementById("ble-calibrate-target-box");
      if (cardEl && typeof cardEl.scrollIntoView === "function") {
        cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      const selectEl = root?.getElementById(
        "ble-calibrate-area-select",
      ) as HTMLSelectElement | null;
      if (selectEl && typeof selectEl.focus === "function") {
        try {
          selectEl.focus({ preventScroll: true });
        } catch {
          selectEl.focus();
        }
      }
    });
  }
}

export function toggleBleLiveStreamOp(store: StudioStoreContext, enabled: boolean): void {
  if (!enabled) {
    store.bleSurveyFrozen.clear();
    for (const dev of store.state?.system_devices || []) {
      if (!dev.subentry_id) continue;
      store.bleSurveyFrozen.set(dev.subentry_id, {
        rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
        packetsSeen: dev.ble_packets_seen ?? 0,
        activeAreaName: dev.active_area_name || "",
      });
    }
    store.bleLiveStreamActive = false;
    store.host.requestUpdate();
    void store.ensureSubscription(false);
    return;
  }
  store.bleSurveyFrozen.clear();
  store.bleLiveStreamActive = true;
  store.host.requestUpdate();
  void store.ensureSubscription(false);
}

export function getActiveSurveyDeviceOp(store: StudioStoreContext): SystemDeviceEntry | undefined {
  const devs = store.state?.system_devices || [];
  const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  return bleDevs.find((d) => d.subentry_id === store.bleSurveySubentryId);
}

export async function setBleScannerOffsetOp(
  store: StudioStoreContext,
  scannerSource: string,
  offsetDb: number,
): Promise<void> {
  const source = String(scannerSource || "").trim();
  if (!source) {
    store.showToast("Missing BLE scanner source", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "set_ble_scanner_offset",
      { scanner_source: source, offset_db: offsetDb },
      store.activeSubentryId || null,
    );
    if (res) {
      if (!store.bleLiveStreamActive && Array.isArray(res.system_devices)) {
        const sourceNorm = source.toLowerCase();
        for (const incomingDev of res.system_devices) {
          if (!incomingDev.subentry_id) continue;
          const frozen = store.bleSurveyFrozen.get(incomingDev.subentry_id);
          if (!frozen) continue;
          const incomingRow = (incomingDev.ble_survey_rows || []).find(
            (r) => String(r.scanner_source || "").trim().toLowerCase() === sourceNorm,
          );
          if (!incomingRow) continue;
          frozen.rows = frozen.rows.map((r) => {
            if (String(r.scanner_source || "").trim().toLowerCase() !== sourceNorm) {
              return r;
            }
            return {
              ...r,
              offset_db: incomingRow.offset_db,
              effective_rssi: incomingRow.effective_rssi,
            };
          });
        }
      }
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update BLE scanner offset"), true);
  }
}

export async function captureBleAreaSignatureOp(
  store: StudioStoreContext,
  areaId: string,
): Promise<void> {
  const sysDevs = store.state?.system_devices;
  const activeDev = Array.isArray(sysDevs)
    ? getActiveSurveyDeviceOp(store) || sysDevs.find((d) => d.ble_tracked || d.kind === "ble_tag")
    : undefined;
  const surveySubentryId = Array.isArray(sysDevs)
    ? activeDev?.subentry_id || ""
    : store.bleSurveySubentryId;
  if (!surveySubentryId) {
    store.showToast("Select a calibration Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "capture_ble_area_signature",
      { area_id: areaId, survey_subentry_id: surveySubentryId },
      store.activeSubentryId || null,
    );
    store.bleCalibrateHandoffActive = false;
    if (res) store.ingestPayload(res, false);
    else store.host?.requestUpdate?.();
    store.showToast("Captured Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Signature capture failed"), true);
  }
}

export async function clearBleAreaSignatureOp(
  store: StudioStoreContext,
  areaId: string,
): Promise<void> {
  const cleanId = String(areaId || "").trim();
  if (!cleanId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "clear_ble_area_signature",
      { area_id: cleanId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Area signature"), true);
  }
}

export function requestClearBleAreaSignatureOp(
  store: StudioStoreContext,
  areaId: string,
  areaName?: string,
): void {
  const cleanId = String(areaId || "").trim();
  if (!cleanId) return;
  const area = areaName || cleanId;
  store.openConfirm({
    kind: "clear_ble_signature",
    title: store.t("confirm.clear_ble_signature.title", { area }),
    consequence: store.t("confirm.clear_ble_signature.body", { area }),
    confirmLabel: store.t("confirm.clear_ble_signature.confirm"),
    danger: true,
    onConfirm: async () => {
      await clearBleAreaSignatureOp(store, cleanId);
    },
  });
}

export async function setAreaFusionOp(
  store: StudioStoreContext,
  areaId: string,
  update: { mode?: string; threshold_pct?: number; sensors?: string[] },
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "set_area_fusion",
      { area_id: areaId, ...update },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.announcePolite(store.t("shell.saved_status"));
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update Area fusion"), true);
  }
}

export async function setAreaIlluminanceOp(
  store: StudioStoreContext,
  areaId: string,
  update: { entity_id?: string; dark_lux?: number; bright_lux?: number },
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "set_area_illuminance",
      { area_id: areaId, ...update },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.announcePolite(store.t("shell.saved_status"));
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update Area ambient light"), true);
  }
}

export async function calibrateAreaIlluminanceOp(
  store: StudioStoreContext,
  calState: IlluminanceCalibrationState,
  areaId?: string,
): Promise<void> {
  if (isCalibratingIlluminanceOp(calState, areaId)) return;
  if (areaId) {
    calState.calibratingIlluminanceAreas.add(areaId);
  } else {
    calState.calibratingAllIlluminance = true;
  }
  store.host.requestUpdate();
  try {
    const payload: Record<string, unknown> = {};
    if (areaId) payload.area_id = areaId;
    const res = await store.ws.runSystemCommand(
      "calibrate_area_illuminance",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    const rawCal = (
      res as unknown as {
        calibrated?: Array<{
          area_name?: string;
          dark_lux?: number;
          bright_lux?: number;
        }>;
      } | null
    )?.calibrated;
    const list = Array.isArray(rawCal) ? rawCal : [];
    const singleItem = list[0];
    if (list.length === 1 && singleItem) {
      store.showToast(
        store.t("presence_sys.calibrate_lux_one_done", {
          area: String(singleItem.area_name || ""),
          dark: String(singleItem.dark_lux ?? 0),
          bright: String(singleItem.bright_lux ?? 40),
        }),
        false,
      );
    } else if (list.length > 1) {
      store.showToast(
        store.t("presence_sys.calibrate_lux_done", { count: list.length }),
        false,
      );
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not calibrate Area ambient light"), true);
  } finally {
    if (areaId) {
      calState.calibratingIlluminanceAreas.delete(areaId);
    } else {
      calState.calibratingAllIlluminance = false;
    }
    store.host.requestUpdate();
  }
}
