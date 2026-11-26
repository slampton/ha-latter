/**
 * Real Chromium Host Harness & `@axe-core/playwright` Helper for `<latter-studio>`.
 *
 * - Intercepts `http://studio.local/**` in-memory via `page.route` (zero TCP ports needed)
 *   serving the real committed `latter-studio.js` and lazy `latter-studio-mdi.js` ESM bundles.
 * - Executes realistic Home Assistant WS state transitions inside Node and bridges `hass.callWS`
 *   & `hass.connection.subscribeMessage` via `page.exposeFunction`.
 */

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DEVICE_PREF_SPECS_CATALOG } from "../src/protocol-schema.js";
import {
  createDefaultMockHubState,
  type MockHubState,
} from "./studio-fixtures.js";
import { buildPayloadFromHub } from "./studio-payload.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_OUT_DIR = path.resolve(__dirname, "..", "..", "custom_components", "latter", "frontend");
const STUDIO_BUNDLE_JS = fs.readFileSync(path.join(FRONTEND_OUT_DIR, "latter-studio.js"), "utf8");
const STUDIO_MDI_JS = fs.readFileSync(path.join(FRONTEND_OUT_DIR, "latter-studio-mdi.js"), "utf8");

// Valid 1x1 teal PNG for thumbnail/crop `<img>` & `<canvas>` loads (`naturalWidth === 1`)
const TINY_PNG_BUF = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

const PREF_GROUP_TIER_BY_KEY = new Map<string, string | null>(
  DEVICE_PREF_SPECS_CATALOG.map((s) => [s.key, s.group_tier]),
);

export interface MountStudioOptions {
  path?: string;
  viewport?: { width: number; height: number };
  darkMode?: boolean;
  dir?: "ltr" | "rtl";
  lang?: string;
  dockedSidebar?: "docked" | "auto" | "always_hidden";
  unitLength?: "km" | "mi";
  customizeHub?: (hub: MockHubState) => void;
}

export interface StudioE2EController {
  readonly hub: MockHubState;
  readonly wsCalls: Array<Record<string, unknown>>;
  readonly uploadedForms: Array<{ authHeader: string }>;
  pushLiveState: (subentryId?: string | null) => Promise<void>;
}

function applyDeviceConfigMutation(
  hub: MockHubState,
  subentryId: string,
  patch: Record<string, unknown>,
  preserveGroup = false,
): void {
  const rec = hub.devices[subentryId];
  if (!rec) return;
  rec.config = { ...rec.config, ...patch };
  rec.deviceConfigRev += 1;

  if ("device_group" in patch) {
    const nextGrp = String(patch.device_group || "custom");
    rec.entry.device_group = nextGrp;
    const grpObj = hub.deviceGroups.find((g) => g.id === nextGrp);
    rec.entry.device_group_name = nextGrp === "custom" ? "Custom" : grpObj?.name || nextGrp;
    if (grpObj?.device_config) {
      for (const [gk, gv] of Object.entries(grpObj.device_config)) {
        if (!(gk in patch) && gv !== undefined) {
          rec.config[gk] = gv;
        }
      }
    }
    return;
  }

  if (!preserveGroup && rec.entry.device_group && rec.entry.device_group !== "custom") {
    const grpObj = hub.deviceGroups.find((g) => g.id === rec.entry.device_group);
    const detaches = Object.keys(patch).some((k) => {
      if (!PREF_GROUP_TIER_BY_KEY.has(k)) return false;
      const tier = PREF_GROUP_TIER_BY_KEY.get(k);
      if (tier === null) return false;
      if (tier === "display" && !grpObj?.include_display) return false;
      if (tier === "interface" && !grpObj?.include_interface) return false;
      return true;
    });
    if (detaches) {
      rec.entry.device_group = "custom";
      rec.entry.device_group_name = "Custom";
      rec.config.device_group = "custom";
    }
  }
}

function handleMockWsCall(hub: MockHubState, msg: Record<string, unknown>): unknown {
  const type = String(msg.type || "");
  if (type === "auth/sign_path") {
    return { path: `${String(msg.path || "")}?authSig=signed_e2e` };
  }
  if (type === "latter/system/get_state") {
    return buildPayloadFromHub(hub, msg.subentry_id as string | null, Boolean(msg.include_logs));
  }
  if (type === "latter/device/export" || type === "latter/system/export") {
    return { bundle: { schema: "latter.backup.v3", version: "3.0.0" } };
  }
  if (type === "latter/device/reset") {
    const subId = String(msg.subentry_id || "");
    return buildPayloadFromHub(hub, subId);
  }
  if (type === "latter/device/command") {
    const subId = String(msg.subentry_id || "");
    const cmd = String(msg.command || "");
    const payload = (msg.payload || {}) as Record<string, unknown>;
    const rec = hub.devices[subId];
    if (rec) {
      if (cmd === "save_device_config" && payload.config && typeof payload.config === "object") {
        applyDeviceConfigMutation(hub, subId, payload.config as Record<string, unknown>);
      } else if (cmd === "device_action") {
        const act = String(payload.action || "");
        if (act === "set_profiler_on" && rec.live.telemetry) rec.live.telemetry.profiler_on = true;
        if (act === "set_profiler_off" && rec.live.telemetry) rec.live.telemetry.profiler_on = false;
        if (act === "activate_screensaver") rec.live.screensaver_active = true;
        if (act === "deactivate_screensaver") rec.live.screensaver_active = false;
      } else if (cmd === "set_device_photo_pool") {
        const target = String(payload.target || "wallpaper");
        const mode = String(payload.mode || "off");
        if (target === "screensaver") {
          rec.config.screensaver_photo_mode = mode;
          if (payload.collection_id !== undefined) {
            rec.config.screensaver_photo_collection = String(payload.collection_id || "");
          }
          if (payload.source_id !== undefined) {
            rec.config.screensaver_photo_source = String(payload.source_id || "");
          }
          if (Array.isArray(payload.photo_ids)) {
            rec.config.screensaver_photo_ids = [...(payload.photo_ids as string[])];
          }
        } else {
          rec.config.wallpaper_mode = mode;
          if (payload.source_id !== undefined) {
            rec.config.wallpaper_source = String(payload.source_id || "");
          }
          if (payload.collection_id !== undefined) {
            rec.config.wallpaper_collection = String(payload.collection_id || "");
          }
          if (Array.isArray(payload.photo_ids)) {
            rec.config.wallpaper_favorites = [...(payload.photo_ids as string[])];
          }
        }
        rec.deviceConfigRev += 1;
      }
    }
    return buildPayloadFromHub(hub, subId);
  }

  if (type === "latter/system/command") {
    const cmd = String(msg.command || "");
    const payload = (msg.payload || {}) as Record<string, unknown>;
    const selectedSub = (msg.subentry_id as string | null) || null;

    if (cmd === "mint_camera_preview_url") {
      const cam = String(payload.camera_entity || "camera.front_entry");
      return {
        camera_entity: cam,
        preview_url: `http://studio.local/api/latter/camera/system?entity_id=${encodeURIComponent(cam)}&sig=ok`,
        expires_in: 600,
      };
    }
    if (cmd === "browse_media_folder") {
      const subpath = String(payload.subpath || "");
      return {
        roots: [{ id: "local", name: "Local Media" }],
        root: String(payload.root || "local"),
        subpath,
        parent_subpath: subpath ? "" : null,
        folders: subpath ? [] : [{ name: "CoastalTrips", subpath: "CoastalTrips" }],
        images: subpath
          ? [
              {
                name: "Lighthouse.jpg",
                relpath: `${subpath}/Lighthouse.jpg`,
                size_bytes: 420_000,
                too_large: false,
                already_imported: false,
                thumb_url: "http://studio.local/thumb/lighthouse.png",
              },
            ]
          : [],
      };
    }
    if (cmd === "save_system_config" && payload.config && typeof payload.config === "object") {
      hub.systemConfig = { ...hub.systemConfig, ...(payload.config as Partial<typeof hub.systemConfig>) };
      hub.systemConfigRev += 1;
    } else if (cmd === "set_area_illuminance") {
      const areaRow = hub.areaPresence.find((r) => r.area_id === payload.area_id);
      if (areaRow) {
        if (payload.entity_id !== undefined) areaRow.illuminance_entity = String(payload.entity_id);
        if (payload.dark_lux !== undefined) areaRow.illuminance_dark_lux = Number(payload.dark_lux);
        if (payload.bright_lux !== undefined) areaRow.illuminance_bright_lux = Number(payload.bright_lux);
      }
    } else if (cmd === "calibrate_area_illuminance") {
      for (const row of hub.areaPresence) {
        if (!payload.area_id || row.area_id === payload.area_id) {
          row.illuminance_dark_lux = 0.6;
          row.illuminance_bright_lux = 52.4;
        }
      }
    } else if (cmd === "set_area_fusion") {
      const areaRow = hub.areaPresence.find((r) => r.area_id === payload.area_id);
      if (areaRow) {
        if (payload.mode !== undefined) areaRow.fusion_mode = String(payload.mode);
        if (payload.threshold_pct !== undefined) areaRow.fusion_threshold_pct = Number(payload.threshold_pct);
        if (Array.isArray(payload.sensors)) areaRow.fusion_sensors = [...(payload.sensors as string[])];
      }
    } else if (cmd === "apply_batch_device_setting" && payload.config && typeof payload.config === "object") {
      const target = String(payload.target || "all");
      for (const id of hub.deviceOrder) {
        const rec = hub.devices[id];
        if (!rec || rec.entry.kind === "ble_tag") continue;
        const matches =
          target === "all" ||
          (target === "online" && rec.entry.is_online) ||
          (target === "roaming" && rec.entry.is_roaming) ||
          (target === "stationary" && !rec.entry.is_roaming) ||
          rec.entry.device_group === target.replace(/^group:/, "");
        if (matches) {
          applyDeviceConfigMutation(hub, id, payload.config as Record<string, unknown>, false);
        }
      }
    } else if (cmd === "create_device_group") {
      const name = String(payload.name || "Group").trim();
      const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_");
      hub.deviceGroups.push({
        id,
        name,
        description: String(payload.description || ""),
        builtin: false,
        include_display: Boolean(payload.include_display),
        include_interface: Boolean(payload.include_interface),
        device_config: {},
      });
    } else if (cmd === "update_group_baseline") {
      const grp = hub.deviceGroups.find((g) => g.id === payload.group_id);
      if (grp) {
        if (payload.include_display !== undefined) grp.include_display = Boolean(payload.include_display);
        if (payload.include_interface !== undefined) grp.include_interface = Boolean(payload.include_interface);
        if (payload.config && typeof payload.config === "object") {
          grp.device_config = { ...(grp.device_config || {}), ...(payload.config as Record<string, unknown>) };
        }
      }
    } else if (cmd === "ignore_discovered_device") {
      const espId = String(payload.esphome_device_id || "");
      const found = hub.discoveredLatter.find((d) => d.esphome_device_id === espId);
      if (found) {
        hub.discoveredLatter = hub.discoveredLatter.filter((d) => d.esphome_device_id !== espId);
        hub.ignoredLatter.push(found);
      }
    } else if (cmd === "unignore_discovered_device") {
      const espId = String(payload.esphome_device_id || "");
      const found = hub.ignoredLatter.find((d) => d.esphome_device_id === espId);
      if (found) {
        hub.ignoredLatter = hub.ignoredLatter.filter((d) => d.esphome_device_id !== espId);
        hub.discoveredLatter.push(found);
      }
    } else if (cmd === "create_photo_collection") {
      const name = String(payload.name || "New Collection");
      const colId = `col_${name.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
      hub.collections.push({ id: colId, name, count: 0 });
      const res = buildPayloadFromHub(hub, selectedSub);
      res.collection = { id: colId, name };
      return res;
    } else if (cmd === "set_security_pin") {
      const pinVal = String(payload.pin || "").trim();
      const targetSub = String(payload.subentry_id || "");
      if (targetSub && hub.devices[targetSub]) {
        hub.devices[targetSub]!.config.has_security_pin = Boolean(pinVal);
      } else {
        hub.hasSecurityPin = Boolean(pinVal);
      }
    }
    return buildPayloadFromHub(hub, selectedSub);
  }

  return buildPayloadFromHub(hub, null);
}

function buildHostHtml(opts: Required<Pick<MountStudioOptions, "darkMode" | "dir" | "lang" | "dockedSidebar" | "unitLength">>): string {
  const themeStyle = opts.darkMode
    ? `
      html {
        background: #111111;
        color: #e1e1e1;
        --primary-background-color: #111111;
        --card-background-color: #1c1c1c;
        --ha-card-background: #1c1c1c;
        --secondary-background-color: #282828;
        --primary-text-color: #e1e1e1;
        --secondary-text-color: #a8a8a8;
        --disabled-text-color: #767676;
        --primary-color: #38bdf8;
        --rgb-primary-color: 56, 189, 248;
        --divider-color: rgba(225, 225, 225, 0.12);
      }`
    : `
      html {
        background: #fafafa;
        color: #212121;
        --primary-background-color: #fafafa;
        --card-background-color: #ffffff;
        --ha-card-background: #ffffff;
        --secondary-background-color: #f0f0f0;
        --primary-text-color: #212121;
        --secondary-text-color: #5f6368;
        --disabled-text-color: #757575;
        --primary-color: #007299;
        --rgb-primary-color: 0, 114, 153;
        --divider-color: rgba(0, 0, 0, 0.12);
      }`;

  return `<!DOCTYPE html>
<html lang="${opts.lang}" dir="${opts.dir}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Latter Studio</title>
  <style>
    html, body { margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
    ${themeStyle}
    ha-icon { display: inline-flex; width: 20px; height: 20px; align-items: center; justify-content: center; }
  </style>
</head>
<body>
  <latter-studio></latter-studio>
  <script type="module">
    if (!customElements.get("ha-icon")) {
      class MockHaIcon extends HTMLElement {
        connectedCallback() {
          if (!this.shadowRoot) {
            const sr = this.attachShadow({ mode: "open" });
            sr.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="currentColor"/></svg>';
          }
        }
      }
      customElements.define("ha-icon", MockHaIcon);
    }

    await import("http://studio.local/latter_ui_3.0.0/latter-studio.js");
    const el = document.querySelector("latter-studio");

    let activeSubCallback = null;
    window.__pushStudioPayload = (payload) => {
      if (typeof activeSubCallback === "function") {
        activeSubCallback(payload);
      }
    };
    window.__openedPopups = [];
    window.open = (url, target) => {
      window.__openedPopups.push({ url: String(url), target: String(target || "") });
      return null;
    };
    window.__toggledSidebarCount = 0;
    window.addEventListener("hass-toggle-menu", () => {
      window.__toggledSidebarCount += 1;
    });

    const syncRouteFromLocation = () => {
      const pathname = window.location.pathname || "/latter";
      const subPath = pathname.startsWith("/latter")
        ? pathname.slice("/latter".length).replace(/^\\/+/, "")
        : "";
      el.route = { prefix: "/latter", path: subPath };
    };

    const hass = {
      user: { id: "admin_1", name: "Alex", is_admin: true },
      auth: {
        data: { access_token: "e2e-admin-bearer-token" },
        expired: false,
        refreshAccessToken: async () => {},
      },
      language: ${JSON.stringify(opts.lang)},
      dockedSidebar: ${JSON.stringify(opts.dockedSidebar)},
      themes: { darkMode: ${JSON.stringify(opts.darkMode)} },
      locale: {
        language: ${JSON.stringify(opts.lang)},
        number_format: "language",
        time_format: "am_pm",
        date_format: "MDY",
        time_zone: "local",
        first_weekday: "sunday",
      },
      config: {
        unit_system: { length: ${JSON.stringify(opts.unitLength)} },
        time_zone: "UTC",
        version: "2026.11.2",
      },
      states: {
        "update.desk_assistant_firmware": {
          entity_id: "update.desk_assistant_firmware",
          state: "off",
          attributes: { installed_version: "3.0.0", latest_version: "3.0.0" },
        },
      },
      localize: (key) => "",
      formatEntityState: (st) => st?.state || "",
      connection: {
        subscribeMessage: async (cb, msg) => {
          activeSubCallback = cb;
          const initial = await window.__nodeSubscribe(msg);
          queueMicrotask(() => {
            if (activeSubCallback === cb && initial) cb(initial);
          });
          return () => {
            if (activeSubCallback === cb) activeSubCallback = null;
          };
        },
        addEventListener: () => {},
        removeEventListener: () => {},
      },
      callWS: (msg) => window.__nodeCallWS(msg),
    };

    el.narrow = window.innerWidth <= 860;
    window.addEventListener("resize", () => {
      el.narrow = window.innerWidth <= 860;
    });
    window.addEventListener("location-changed", syncRouteFromLocation);
    window.addEventListener("popstate", syncRouteFromLocation);

    syncRouteFromLocation();
    el.hass = hass;
  </script>
</body>
</html>`;
}

const PAGE_BRIDGES = new WeakMap<
  Page,
  {
    onSubscribe: (msg: Record<string, unknown>) => unknown;
    onCallWS: (msg: Record<string, unknown>) => unknown;
  }
>();

export async function mountStudio(
  page: Page,
  options: MountStudioOptions = {},
): Promise<StudioE2EController> {
  const viewport = options.viewport ?? { width: 1440, height: 900 };
  const darkMode = options.darkMode ?? false;
  const dir = options.dir ?? "ltr";
  const lang = options.lang ?? "en";
  const dockedSidebar = options.dockedSidebar ?? "docked";
  const unitLength = options.unitLength ?? "km";
  const initialPath = options.path ?? "/latter";

  await page.setViewportSize(viewport);

  const hub = createDefaultMockHubState();
  options.customizeHub?.(hub);

  const wsCalls: Array<Record<string, unknown>> = [];
  const uploadedForms: Array<{ authHeader: string }> = [];
  let lastSubentryId: string | null = null;

  const onSubscribe = (msg: Record<string, unknown>): unknown => {
    wsCalls.push(structuredClone(msg));
    lastSubentryId = (msg.subentry_id as string | null) ?? null;
    return buildPayloadFromHub(hub, lastSubentryId, Boolean(msg.include_logs));
  };
  const onCallWS = (msg: Record<string, unknown>): unknown => {
    wsCalls.push(structuredClone(msg));
    return handleMockWsCall(hub, msg);
  };

  const existingBridge = PAGE_BRIDGES.get(page);
  if (existingBridge) {
    existingBridge.onSubscribe = onSubscribe;
    existingBridge.onCallWS = onCallWS;
    await page.unroute("http://studio.local/**");
  } else {
    const bridge = { onSubscribe, onCallWS };
    PAGE_BRIDGES.set(page, bridge);
    await page.exposeFunction("__nodeSubscribe", (msg: Record<string, unknown>) =>
      bridge.onSubscribe(msg),
    );
    await page.exposeFunction("__nodeCallWS", (msg: Record<string, unknown>) =>
      bridge.onCallWS(msg),
    );
  }

  const hostHtml = buildHostHtml({ darkMode, dir, lang, dockedSidebar, unitLength });

  await page.route("http://studio.local/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.pathname === "/latter_ui_3.0.0/latter-studio.js") {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript; charset=utf-8",
        body: STUDIO_BUNDLE_JS,
      });
      return;
    }
    if (url.pathname === "/latter_ui_3.0.0/latter-studio-mdi.js") {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript; charset=utf-8",
        body: STUDIO_MDI_JS,
      });
      return;
    }
    if (url.pathname === "/api/latter/wallpaper/upload" && req.method() === "POST") {
      const authHeader = req.headers()["authorization"] || "";
      uploadedForms.push({ authHeader });
      const newPhoto = {
        id: `photo:upload_${uploadedForms.length}`,
        name: `Uploaded Photo ${uploadedForms.length}`,
        kind: "uploaded",
        source_kind: "upload",
        deletable: true,
        thumb_url: "http://studio.local/thumb/uploaded.png",
        collections: [],
      };
      hub.photos.push(newPhoto);
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          ok: true,
          photo_id: newPhoto.id,
          photo: newPhoto,
          system_wallpapers: hub.photos,
          wallpapers: hub.photos,
          photo_collections: hub.collections,
        }),
      });
      return;
    }
    if (url.pathname.startsWith("/thumb/") || url.pathname.startsWith("/orig/") || url.pathname.startsWith("/api/latter/camera/")) {
      await route.fulfill({
        status: 200,
        contentType: "image/png",
        body: TINY_PNG_BUF,
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "text/html; charset=utf-8",
      body: hostHtml,
    });
  });

  await page.goto(`http://studio.local${initialPath}`);
  await page.locator("latter-studio #studio-root:not(.is-loading)").waitFor({ state: "visible" });

  return {
    hub,
    wsCalls,
    uploadedForms,
    pushLiveState: async (subentryId?: string | null) => {
      const payload = buildPayloadFromHub(hub, subentryId ?? lastSubentryId);
      await page.evaluate((p) => {
        (window as unknown as { __pushStudioPayload: (v: unknown) => void }).__pushStudioPayload(p);
      }, payload);
    },
  };
}

export async function expectZeroAxeViolations(page: Page, contextLabel: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .include("latter-studio")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();

  const summary = results.violations.map(
    (v) =>
      `[${v.id} (${v.impact})] ${v.help} -> ${v.nodes
        .slice(0, 3)
        .map((n) => `${JSON.stringify(n.target)}: ${n.failureSummary}`)
        .join(" | ")}`,
  );
  expect(summary, `WCAG 2.2 AA violations on ${contextLabel}:\n${summary.join("\n")}`).toEqual([]);
}

export async function expectZeroHorizontalOverflow(page: Page, contextLabel: string): Promise<void> {
  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(
    metrics.scrollWidth,
    `Horizontal overflow detected on ${contextLabel}: scrollWidth=${metrics.scrollWidth} > innerWidth=${metrics.innerWidth}`,
  ).toBeLessThanOrEqual(metrics.innerWidth);
}
