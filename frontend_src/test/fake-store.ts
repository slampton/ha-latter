/**
 * Typed `makeFakeStore()` + `renderToHtml()` test helper implementing the full `StudioStore`
 * (`store.entity`, `store.groups`, `store.tools`, `store.t`, `store.tPrefLabel`, `store.tPrefOption`)
 * surface for both `node --test` and `ha-latter/tests/test_studio_runtime.py` (`A-13`, `A-17`).
 */

import "./dom-shim.js";
import { STUDIO_REV } from "../src/constants.js";
import { render as litRender, type RenderRootNode } from "../src/lib/lit.js";
import { StudioStore } from "../src/state/store.js";
import type {
  DevicePrefItem,
  EspHomeEntityItem,
  HomeAssistant,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
} from "../src/types.js";
import { simDocument, SimElement } from "./dom-shim.js";

interface EspHomeSection {
  id: string;
  title: string;
  items: EspHomeEntityItem[];
}

export interface FakeStoreOptions {
  activeSubentryId?: string;
  currentScope?: StudioScope;
  currentViewId?: StudioViewId;
  deviceSelected?: boolean;
  hass?: Partial<HomeAssistant> | null;
  state?: Record<string, unknown>;
  sections?: Record<string, EspHomeEntityItem[]>;
  devicePrefs?: DevicePrefItem[];
}

export interface FakeStoreHarness {
  store: StudioStore;
  host: {
    isConnected: boolean;
    requestCount: number;
    requestUpdate: () => void;
    addController: () => void;
    removeController: () => void;
    updateComplete: Promise<boolean>;
    renderRoot: SimElement;
  };
  sysCalls: Array<{ command: string; payload: Record<string, unknown> }>;
  devCalls: Array<{ subentryId: string; command: string; payload: Record<string, unknown> }>;
  toasts: Array<{ msg: string; isError: boolean }>;
  scrolled: Array<{ id: string; opts: unknown }>;
  focused: Array<{ id: string; opts: unknown }>;
}

function inferDevicePrefsFromSections(
  sections: Record<string, EspHomeEntityItem[]>,
): DevicePrefItem[] {
  const out: DevicePrefItem[] = [];
  const seen = new Set<string>();

  for (const [secId, items] of Object.entries(sections)) {
    for (const it of items) {
      if (it.domain !== "select" && it.domain !== "switch" && it.domain !== "number") {
        continue;
      }
      let key = it.pref_key || it.key || "";
      if (!key && it.entity_id) {
        const objId =
          (it.entity_id.includes(".") ? it.entity_id.split(".", 2)[1] : it.entity_id) ||
          it.entity_id;
        // Strip leading `<slug>_<section>_` prefix such as `pocket_display_clock_face`
        const parts = objId.split("_");
        key = parts.length >= 3 ? parts.slice(2).join("_") : objId;
        if (secId === "voice" && key === "visual_profile") key = "va_visual_profile";
        if (secId === "music" && !key.startsWith("music_") && !key.endsWith("_sort_order")) {
          if (key === "overlay_style") {
            key = `music_${key}`;
          }
        }
        if (secId === "home" && (key === "sun" || key === "moon")) {
          key = `home_${key}`;
        }
      }
      if (!key || seen.has(key)) continue;
      seen.add(key);

      let val: unknown = it.state;
      if (it.domain === "switch") {
        val = it.state === "on" || it.state === "true";
      } else if (it.domain === "number") {
        const n = Number(it.state);
        val = Number.isFinite(n) ? n : 0;
      }

      out.push({
        key,
        label: (it.name || key).replace(/^(?:Voice|Display|Home|Sleep & Wake|Music):\s*/i, ""),
        section: secId,
        domain: it.domain,
        value: val as string | number | boolean,
        options: it.options ? [...it.options] : undefined,
        min: it.min ?? undefined,
        max: it.max ?? undefined,
        step: it.step ?? undefined,
        unit: it.unit ?? undefined,
      });
    }
  }
  return out;
}

export function makeFakeStore(opts: FakeStoreOptions = {}): FakeStoreHarness {
  const scrolled: Array<{ id: string; opts: unknown }> = [];
  const focused: Array<{ id: string; opts: unknown }> = [];
  const sysCalls: Array<{ command: string; payload: Record<string, unknown> }> = [];
  const devCalls: Array<{ subentryId: string; command: string; payload: Record<string, unknown> }> =
    [];
  const toasts: Array<{ msg: string; isError: boolean }> = [];

  const renderRoot = simDocument.createElement("div");
  const origGetById = renderRoot.getElementById.bind(renderRoot);
  renderRoot.getElementById = (id: string) => {
    const existing = origGetById(id);
    if (existing) return existing;
    const proxyEl = simDocument.createElement("div");
    proxyEl.id = id;
    proxyEl.scrollIntoView = (scrollOpts?: unknown) => {
      scrolled.push({ id, opts: scrollOpts ?? null });
    };
    (proxyEl as unknown as { focus: (focusOpts?: unknown) => void }).focus = (
      focusOpts?: unknown,
    ) => {
      focused.push({ id, opts: focusOpts ?? null });
    };
    return proxyEl;
  };

  const host = {
    isConnected: true,
    requestCount: 0,
    requestUpdate(): void {
      host.requestCount += 1;
    },
    addController(): void {},
    removeController(): void {},
    updateComplete: Promise.resolve(true),
    renderRoot,
  };

  const store = new StudioStore(host as unknown as ConstructorParameters<typeof StudioStore>[0]);
  store.ensureSubscription = async () => {};

  const hassObj = (opts.hass ?? {
    locale: { language: "en" },
    config: { unit_system: { length: "km" } },
    states: {},
  }) as HomeAssistant;
  store.ws.setHass(hassObj);

  store.ws.runSystemCommand = async (command, payload = {}) => {
    sysCalls.push({ command, payload: structuredClone(payload) });
    return structuredClone(store.state) as StudioStatePayload;
  };
  store.ws.runDeviceCommand = async (subentryId, command, payload = {}) => {
    devCalls.push({ subentryId, command, payload: structuredClone(payload) });
    return structuredClone(store.state) as StudioStatePayload;
  };
  store.ws.mintCameraPreviewUrl = async (cameraEntity) => ({
    camera_entity: cameraEntity,
    preview_url: `/api/latter/camera/system?entity_id=${encodeURIComponent(cameraEntity)}&sig=fake`,
    expires_in: 600,
  });
  store.ws.browseMediaFolder = async (root, subpath) => ({
    roots: [{ id: "local", name: "Media" }],
    root: root || "local",
    subpath: subpath || "",
    parent_subpath: null,
    folders: [],
    images: [],
  });

  const origShowToast = store.showToast.bind(store);
  store.showToast = (msg: string, isError = false) => {
    toasts.push({ msg, isError: Boolean(isError) });
    origShowToast(msg, isError);
  };

  const sectionEntries: EspHomeSection[] = opts.sections
    ? Object.entries(opts.sections).map(([id, items]) => ({
        id,
        title: id,
        items,
      }))
    : [];

  const rawState = (opts.state || {}) as Record<string, unknown>;
  const existingEsp = (rawState.esphome as Record<string, unknown> | undefined) || {};
  const mergedSections =
    (existingEsp.sections as EspHomeSection[] | undefined) ?? sectionEntries;
  const mergedPrefs =
    opts.devicePrefs ??
    (rawState.device_prefs as DevicePrefItem[] | undefined) ??
    (opts.sections ? inferDevicePrefsFromSections(opts.sections) : []);

  if (opts.activeSubentryId !== undefined) {
    store.activeSubentryId = opts.activeSubentryId;
  }
  if (opts.currentScope !== undefined) {
    store.currentScope = opts.currentScope;
  }
  if (opts.currentViewId !== undefined) {
    store.currentViewId = opts.currentViewId;
  }
  if (opts.deviceSelected !== undefined) {
    store.deviceSelected = opts.deviceSelected;
  }

  const fullPayload = {
    studio_rev: STUDIO_REV,
    system_config_rev: 1,
    device_config_rev: 1,
    subentry_id: opts.activeSubentryId ?? (rawState.subentry_id as string | undefined) ?? "sub_1",
    config: {},
    capabilities: { has_display: true, has_audio: true, has_power: true },
    live: {},
    system_config: {},
    system_devices: [],
    device_groups: [],
    photo_collections: [],
    wallpapers: [],
    system_wallpapers: [],
    discovered_latter_devices: [],
    ignored_latter_devices: [],
    discovered_ble_devices: [],
    ble_area_signatures: [],
    catalog: {
      areas: [],
      persons: [],
      ma_speakers: [],
      ma_players: [],
      remotes: [],
      volume_targets: [],
      alarms: [],
      cameras: [],
      climates: [],
      locks: [],
      garages: [],
      vacuums: [],
      weathers: [],
      calendars: [],
      shortcut_entities: [],
    },
    ...rawState,
    esphome: {
      ...existingEsp,
      sections: mergedSections,
    },
    device_prefs: mergedPrefs,
  } as unknown as StudioStatePayload;

  store.ingestPayload(fullPayload, false);

  // Re-apply explicit scope/view/subentry overrides if `ingestPayload` adjusted defaults
  if (opts.activeSubentryId !== undefined) {
    store.activeSubentryId = opts.activeSubentryId;
  }
  if (opts.currentScope !== undefined) {
    store.currentScope = opts.currentScope;
  }
  if (opts.currentViewId !== undefined) {
    store.currentViewId = opts.currentViewId;
  }
  if (opts.deviceSelected !== undefined) {
    store.deviceSelected = opts.deviceSelected;
  }

  return { store, host, sysCalls, devCalls, toasts, scrolled, focused };
}

export function render(tpl: unknown, container: SimElement): void {
  litRender(tpl, container as unknown as RenderRootNode);
}

export function renderToContainer(tpl: unknown): SimElement {
  const container = simDocument.createElement("div");
  render(tpl, container);
  return container;
}

export function renderToHtml(tpl: unknown): string {
  const container = renderToContainer(tpl);
  return container.innerHTML.replace(/<!--[\s\S]*?-->/g, "");
}
