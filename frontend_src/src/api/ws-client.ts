/**
 * Admin-gated WebSocket & Bearer-authenticated XHR multipart client for Latter Studio (`D-025`, `D-065`).
 * - Sends mandatory `studio_rev: STUDIO_REV` (`34`) on all 9 WS endpoints
 * - Enforces literal-union & runtime `SYSTEM_WS_COMMANDS` / `DEVICE_WS_COMMANDS` checks (`A-25`)
 * - Applies per-command `Promise.race` timeouts (`15_000 ms` standard, `60_000 ms` import/reset/update) (`B-15`)
 * - Supports on-demand 600 s `mint_camera_preview_url`, Discovered `ignore`/`unignore`, & `expected_config_rev`
 */

import { MAX_WALLPAPER_UPLOAD_BYTES } from "../constants.js";
import {
  DEVICE_WS_COMMANDS,
  STUDIO_REV,
  SYSTEM_WS_COMMANDS,
} from "../protocol-schema.js";
import type { HomeAssistant, StudioScope, StudioStatePayload, WallpaperItem } from "../types.js";

export { DEVICE_WS_COMMANDS, SYSTEM_WS_COMMANDS };

export const WS_STANDARD_TIMEOUT_MS = 15_000;
export const WS_LONG_TIMEOUT_MS = 60_000;

export type SystemWsCommand =
  | "set_ble_scanner_offset"
  | "set_area_fusion"
  | "capture_ble_area_signature"
  | "clear_ble_area_signature"
  | "system_entity_action"
  | "send_announcement"
  | "check_system_updates"
  | "clear_internal_logs"
  | "remove_device"
  | "add_latter_device"
  | "ignore_discovered_device"
  | "unignore_discovered_device"
  | "add_ble_device"
  | "create_device_group"
  | "delete_device_group"
  | "update_group_baseline"
  | "apply_batch_device_setting"
  | "test_doorbell_speaker"
  | "mint_camera_preview_url"
  | "delete_wallpaper"
  | "save_system_config"
  | "rotate_signing_key"
  | "set_security_pin";

export type DeviceWsCommand =
  | "esphome_entity_action"
  | "device_action"
  | "select_wallpaper"
  | "toggle_wallpaper_favorite"
  | "save_device_config";

export interface WsErrorLike {
  code?: string;
  message?: string;
}

export function isStudioRevMismatchError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const code = String((err as WsErrorLike).code || "");
  return code === "studio_rev_mismatch" || code === "version_mismatch";
}

export function isConflictError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  return String((err as WsErrorLike).code || "") === "conflict";
}

export function formatWsError(err: unknown, fallback = "Action failed"): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err === "object" && "message" in err && (err as WsErrorLike).message) {
    return String((err as WsErrorLike).message);
  }
  return fallback;
}

export interface MintCameraPreviewResult {
  camera_entity: string;
  preview_url: string;
  expires_in: number;
}

export interface UploadWallpaperResult {
  ok: boolean;
  filename?: string;
  source_id?: string;
  wallpapers?: WallpaperItem[];
  system_wallpapers?: WallpaperItem[];
}

function withWsTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      reject(
        new Error(
          "Request timed out — check your Home Assistant connection and try again.",
        ),
      );
    }, timeoutMs);
  });
  return Promise.race([promise, timeoutPromise]).finally(() => {
    if (timer !== null) {
      clearTimeout(timer);
    }
  });
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

  private async callWS<T>(
    msg: Record<string, unknown>,
    timeoutMs = WS_STANDARD_TIMEOUT_MS,
  ): Promise<T> {
    const hass = this.requireHass();
    try {
      return await withWsTimeout(hass.callWS<T>(msg), timeoutMs);
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
  }): Promise<StudioStatePayload> {
    return this.callWS<StudioStatePayload>({
      type: "latter/system/get_state",
      subentry_id: options.subentryId || null,
      include_logs: Boolean(options.includeLogs),
      studio_rev: STUDIO_REV,
    });
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
      return await withWsTimeout(
        hass.connection.subscribeMessage(onEvent, msg),
        WS_STANDARD_TIMEOUT_MS,
      );
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }

  async runSystemCommand(
    cmd: Exclude<SystemWsCommand, "mint_camera_preview_url">,
    payload: Record<string, unknown> = {},
    selectedSubentryId?: string | null,
  ): Promise<StudioStatePayload> {
    if (!SYSTEM_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown System command: ${cmd}`);
    }
    const timeoutMs =
      cmd === "check_system_updates" ? WS_LONG_TIMEOUT_MS : WS_STANDARD_TIMEOUT_MS;
    return this.callWS<StudioStatePayload>(
      {
        type: "latter/system/command",
        command: cmd,
        subentry_id: selectedSubentryId || null,
        payload,
        studio_rev: STUDIO_REV,
      },
      timeoutMs,
    );
  }

  async mintCameraPreviewUrl(cameraEntity: string): Promise<MintCameraPreviewResult> {
    if (!SYSTEM_WS_COMMANDS.has("mint_camera_preview_url")) {
      throw new Error("mint_camera_preview_url is not registered in Studio protocol contract");
    }
    return this.callWS<MintCameraPreviewResult>({
      type: "latter/system/command",
      command: "mint_camera_preview_url",
      subentry_id: null,
      payload: { camera_entity: cameraEntity },
      studio_rev: STUDIO_REV,
    });
  }

  async runDeviceCommand(
    subentryId: string,
    cmd: DeviceWsCommand,
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

  async exportBackup(
    scope: StudioScope,
    subentryId?: string,
  ): Promise<{ bundle: Record<string, unknown> }> {
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
  }): Promise<StudioStatePayload> {
    if (options.scope === "device") {
      if (!options.targetSubentryId) {
        throw new Error("Choose the Device to restore this backup onto");
      }
      return this.callWS<StudioStatePayload>(
        {
          type: "latter/device/import",
          subentry_id: options.targetSubentryId,
          bundle: options.bundle,
          studio_rev: STUDIO_REV,
        },
        WS_LONG_TIMEOUT_MS,
      );
    }
    return this.callWS<StudioStatePayload>(
      {
        type: "latter/system/import",
        subentry_id: options.selectedSubentryId || null,
        bundle: options.bundle,
        studio_rev: STUDIO_REV,
      },
      WS_LONG_TIMEOUT_MS,
    );
  }

  async resetDevice(options: {
    subentryId: string;
    deviceSettings: boolean;
    latterOptions: boolean;
  }): Promise<StudioStatePayload> {
    return this.callWS<StudioStatePayload>(
      {
        type: "latter/device/reset",
        subentry_id: options.subentryId,
        device_settings: options.deviceSettings,
        latter_options: options.latterOptions,
        studio_rev: STUDIO_REV,
      },
      WS_LONG_TIMEOUT_MS,
    );
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

  private async getAccessToken(forceRefresh = false): Promise<string> {
    const hass = this.requireHass();
    const auth = hass.auth;
    if (!auth) {
      throw new Error("Home Assistant authentication session is not ready");
    }
    if ((forceRefresh || auth.expired) && typeof auth.refreshAccessToken === "function") {
      await auth.refreshAccessToken();
    }
    const token = auth.data?.access_token;
    if (!token) {
      throw new Error("Home Assistant access token is unavailable");
    }
    return token;
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

    const UPLOAD_PATH = "/api/latter/wallpaper/upload";
    const form = new FormData();
    form.append("file", options.file, options.file.name || "wallpaper.jpg");
    form.append("scope", options.scope);
    if (options.subentryId) {
      form.append("subentry_id", options.subentryId);
    }

    const sendOnce = (bearerToken: string) =>
      new Promise<{ status: number; body: Record<string, unknown> | null }>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", UPLOAD_PATH, true);
        xhr.setRequestHeader("Authorization", `Bearer ${bearerToken}`);
        xhr.responseType = "json";
        xhr.timeout = WS_LONG_TIMEOUT_MS;
        if (xhr.upload && options.onProgress) {
          xhr.upload.onprogress = (ev: ProgressEvent) => {
            if (ev.lengthComputable && ev.total > 0) {
              options.onProgress?.(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
            }
          };
        }
        xhr.onload = () => {
          const body =
            xhr.response && typeof xhr.response === "object"
              ? (xhr.response as Record<string, unknown>)
              : null;
          resolve({ status: xhr.status, body });
        };
        xhr.onerror = () => {
          reject(new Error("Network error while uploading wallpaper"));
        };
        xhr.ontimeout = () => {
          reject(new Error("Wallpaper upload timed out"));
        };
        xhr.onabort = () => {
          reject(new Error("Wallpaper upload was canceled"));
        };
        xhr.send(form);
      });

    let token = await this.getAccessToken(false);
    let response = await sendOnce(token);
    if (
      response.status === 401 &&
      typeof this.hassRef?.auth?.refreshAccessToken === "function"
    ) {
      token = await this.getAccessToken(true);
      response = await sendOnce(token);
    }

    const { status, body } = response;
    if (status >= 200 && status < 300) {
      options.onProgress?.(100);
      return {
        ok: true,
        filename: body?.filename ? String(body.filename) : undefined,
        source_id: body?.source_id ? String(body.source_id) : undefined,
        wallpapers: Array.isArray(body?.wallpapers) ? (body.wallpapers as WallpaperItem[]) : undefined,
        system_wallpapers: Array.isArray(body?.system_wallpapers)
          ? (body.system_wallpapers as WallpaperItem[])
          : undefined,
      };
    }
    const errMsg = body?.error
      ? String(body.error)
      : body?.message
        ? String(body.message)
        : `Wallpaper upload failed (HTTP ${status})`;
    throw new Error(errMsg);
  }
}
