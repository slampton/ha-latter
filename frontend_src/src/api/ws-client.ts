/**
 * Admin-gated WebSocket & signed XHR multipart client for Latter Studio.
 * Enforces `studio_rev` on every read/mutation call and surfaces `studio_rev_mismatch`.
 */

import { MAX_WALLPAPER_UPLOAD_BYTES, STUDIO_REV } from "../constants.js";
import type { HomeAssistant, StudioScope, StudioStatePayload, WallpaperItem } from "../types.js";

export const SYSTEM_WS_COMMANDS = new Set([
  "set_ble_area_offset",
  "set_area_fusion",
  "auto_calibrate_here",
  "system_entity_action",
  "send_announcement",
  "check_system_updates",
  "clear_internal_logs",
  "remove_device",
  "add_ble_device",
  "set_device_remote_group",
  "create_device_group",
  "delete_device_group",
  "sync_device_group",
  "seed_group_baseline",
  "set_group_device_setting",
  "test_doorbell_speaker",
  "upload_system_wallpaper",
  "delete_system_wallpaper",
  "save_system_config",
  "rotate_signing_key",
  "set_security_pin",
]);

export const DEVICE_WS_COMMANDS = new Set([
  "esphome_entity_action",
  "upload_wallpaper",
  "select_wallpaper",
  "toggle_wallpaper_favorite",
  "delete_wallpaper",
  "save_device_config",
]);

// Explicit command registry descriptor table (also verified statically by `[STUDIO COMMANDS]`).
export const STUDIO_COMMAND_DESCRIPTORS = [
  { scope: "system" as const, command: "set_ble_area_offset" },
  { scope: "system" as const, command: "set_area_fusion" },
  { scope: "system" as const, command: "auto_calibrate_here" },
  { scope: "system" as const, command: "system_entity_action" },
  { scope: "system" as const, command: "send_announcement" },
  { scope: "system" as const, command: "check_system_updates" },
  { scope: "system" as const, command: "clear_internal_logs" },
  { scope: "system" as const, command: "remove_device" },
  { scope: "system" as const, command: "add_ble_device" },
  { scope: "system" as const, command: "set_device_remote_group" },
  { scope: "system" as const, command: "create_device_group" },
  { scope: "system" as const, command: "delete_device_group" },
  { scope: "system" as const, command: "sync_device_group" },
  { scope: "system" as const, command: "seed_group_baseline" },
  { scope: "system" as const, command: "set_group_device_setting" },
  { scope: "system" as const, command: "test_doorbell_speaker" },
  { scope: "system" as const, command: "upload_system_wallpaper" },
  { scope: "system" as const, command: "delete_system_wallpaper" },
  { scope: "system" as const, command: "save_system_config" },
  { scope: "system" as const, command: "rotate_signing_key" },
  { scope: "system" as const, command: "set_security_pin" },
  { scope: "device" as const, command: "esphome_entity_action" },
  { scope: "device" as const, command: "upload_wallpaper" },
  { scope: "device" as const, command: "select_wallpaper" },
  { scope: "device" as const, command: "toggle_wallpaper_favorite" },
  { scope: "device" as const, command: "delete_wallpaper" },
  { scope: "device" as const, command: "save_device_config" },
] as const;

export interface WsErrorLike {
  code?: string;
  message?: string;
}

export function isStudioRevMismatchError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const code = String((err as WsErrorLike).code || "");
  return code === "studio_rev_mismatch";
}

export function formatWsError(err: unknown, fallback = "Action failed"): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err === "object" && "message" in err && (err as WsErrorLike).message) {
    return String((err as WsErrorLike).message);
  }
  return fallback;
}

export interface UploadWallpaperResult {
  ok: boolean;
  filename?: string;
  source_id?: string;
  wallpapers?: WallpaperItem[];
  system_wallpapers?: WallpaperItem[];
}

export class StudioWsClient {
  private hassRef: HomeAssistant | null = null;
  private readonly onRevMismatch: () => void;

  constructor(onRevMismatch: () => void) {
    this.onRevMismatch = onRevMismatch;
  }

  setHass(hass: HomeAssistant | null): void {
    this.hassRef = hass;
  }

  get hass(): HomeAssistant | null {
    return this.hassRef;
  }

  private requireHass(): HomeAssistant {
    if (!this.hassRef) {
      throw new Error("Home Assistant connection is not ready");
    }
    return this.hassRef;
  }

  private async callWS<T>(msg: Record<string, unknown>): Promise<T> {
    const hass = this.requireHass();
    try {
      return await hass.callWS<T>(msg);
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }

  async getState(options: {
    subentryId?: string | null;
    includeLogs?: boolean;
  }): Promise<StudioStatePayload | null> {
    const res = await this.callWS<StudioStatePayload | null>({
      type: "latter/system/get_state",
      subentry_id: options.subentryId || null,
      include_logs: Boolean(options.includeLogs),
      studio_rev: STUDIO_REV,
    });
    if (res === null) {
      this.onRevMismatch();
    }
    return res;
  }

  async subscribe(
    options: {
      subentryId?: string | null;
      surveySubentryId?: string | null;
      includeLogs?: boolean;
    },
    onEvent: (payload: unknown) => void,
  ): Promise<() => void> {
    const hass = this.requireHass();
    if (!hass.connection) {
      throw new Error("Home Assistant WebSocket connection is unavailable");
    }
    try {
      const msg: Record<string, unknown> = {
        type: "latter/system/subscribe",
        subentry_id: options.subentryId || null,
        include_logs: Boolean(options.includeLogs),
        studio_rev: STUDIO_REV,
      };
      if (options.surveySubentryId) {
        msg.survey_subentry_id = options.surveySubentryId;
      }
      return await hass.connection.subscribeMessage(onEvent, msg);
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }

  async runSystemCommand(
    cmd: string,
    payload: Record<string, unknown> = {},
    selectedSubentryId?: string | null,
  ): Promise<StudioStatePayload> {
    if (!SYSTEM_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown System command: ${cmd}`);
    }
    return this.callWS<StudioStatePayload>({
      type: "latter/system/command",
      command: cmd,
      subentry_id: selectedSubentryId || null,
      payload,
      studio_rev: STUDIO_REV,
    });
  }

  async runDeviceCommand(
    subentryId: string,
    cmd: string,
    payload: Record<string, unknown> = {},
  ): Promise<StudioStatePayload> {
    if (!DEVICE_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown Device command: ${cmd}`);
    }
    if (!subentryId) {
      throw new Error("Choose a Device first");
    }
    return this.callWS<StudioStatePayload>({
      type: "latter/device/command",
      command: cmd,
      subentry_id: subentryId,
      payload,
      studio_rev: STUDIO_REV,
    });
  }

  async exportBackup(scope: StudioScope, subentryId?: string): Promise<{ bundle: Record<string, unknown> }> {
    if (scope === "device") {
      if (!subentryId) throw new Error("Choose a Device to export");
      return this.callWS<{ bundle: Record<string, unknown> }>({
        type: "latter/device/export",
        subentry_id: subentryId,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS<{ bundle: Record<string, unknown> }>({
      type: "latter/system/export",
      studio_rev: STUDIO_REV,
    });
  }

  async importBackup(options: {
    scope: StudioScope;
    bundle: Record<string, unknown>;
    targetSubentryId?: string | null;
    selectedSubentryId?: string | null;
    restoreEspHomeEntities: boolean;
  }): Promise<StudioStatePayload> {
    if (options.scope === "device") {
      if (!options.targetSubentryId) {
        throw new Error("Choose the Device to restore this backup onto");
      }
      return this.callWS<StudioStatePayload>({
        type: "latter/device/import",
        subentry_id: options.targetSubentryId,
        bundle: options.bundle,
        restore_esphome_entities: options.restoreEspHomeEntities,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS<StudioStatePayload>({
      type: "latter/system/import",
      subentry_id: options.selectedSubentryId || null,
      bundle: options.bundle,
      restore_esphome_entities: options.restoreEspHomeEntities,
      studio_rev: STUDIO_REV,
    });
  }

  async resetDevice(options: {
    subentryId: string;
    deviceSettings: boolean;
    latterOptions: boolean;
  }): Promise<StudioStatePayload> {
    return this.callWS<StudioStatePayload>({
      type: "latter/device/reset",
      subentry_id: options.subentryId,
      device_settings: options.deviceSettings,
      latter_options: options.latterOptions,
      studio_rev: STUDIO_REV,
    });
  }

  async signHaPath(path: string, expires = 300): Promise<string> {
    const signed = await this.callWS<{ path: string }>({
      type: "auth/sign_path",
      path,
      expires,
    });
    if (!signed || !signed.path) {
      throw new Error("Could not sign Home Assistant path");
    }
    return signed.path;
  }

  async uploadWallpaperMultipart(options: {
    scope: StudioScope;
    subentryId?: string;
    file: File;
    onProgress?: (percent: number) => void;
  }): Promise<UploadWallpaperResult> {
    if (!options.file) {
      throw new Error("Choose an image file first");
    }
    if (options.file.size > MAX_WALLPAPER_UPLOAD_BYTES) {
      throw new Error("Wallpaper image must be 15 MB or smaller");
    }
    if (options.scope === "device" && !options.subentryId) {
      throw new Error("Choose a Device before uploading a Device wallpaper");
    }
    const signedUrl = await this.signHaPath("/api/latter/wallpaper/upload", 300);
    const form = new FormData();
    form.append("file", options.file, options.file.name || "wallpaper.jpg");
    form.append("scope", options.scope);
    if (options.subentryId) {
      form.append("subentry_id", options.subentryId);
    }

    return new Promise<UploadWallpaperResult>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", signedUrl, true);
      xhr.responseType = "json";
      if (xhr.upload && options.onProgress) {
        xhr.upload.onprogress = (ev: ProgressEvent) => {
          if (ev.lengthComputable && ev.total > 0) {
            options.onProgress?.(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
          }
        };
      }
      xhr.onload = () => {
        const body = xhr.response && typeof xhr.response === "object"
          ? (xhr.response as Record<string, unknown>)
          : null;
        if (xhr.status >= 200 && xhr.status < 300) {
          options.onProgress?.(100);
          resolve({
            ok: true,
            filename: body?.filename ? String(body.filename) : undefined,
            source_id: body?.source_id ? String(body.source_id) : undefined,
            wallpapers: Array.isArray(body?.wallpapers) ? (body.wallpapers as WallpaperItem[]) : undefined,
            system_wallpapers: Array.isArray(body?.system_wallpapers)
              ? (body.system_wallpapers as WallpaperItem[])
              : undefined,
          });
          return;
        }
        const errMsg = body?.error
          ? String(body.error)
          : body?.message
            ? String(body.message)
            : `Wallpaper upload failed (HTTP ${xhr.status})`;
        reject(new Error(errMsg));
      };
      xhr.onerror = () => {
        reject(new Error("Network error while uploading wallpaper"));
      };
      xhr.onabort = () => {
        reject(new Error("Wallpaper upload was canceled"));
      };
      xhr.send(form);
    });
  }
}
