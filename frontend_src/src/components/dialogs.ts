/**
 * Native `<dialog>` Modals for Latter Studio:
 * - Remove Device, Reset Device, Add BLE Tag, Custom Color Wheel, Save Custom Group
 * - Custom Dock / Pinned Shortcut Modal (`#latter-shortcut-modal`)
 * - Native App Configuration Modal (`#latter-app-config-modal`, D-053)
 * Uses component-scoped pointer capture on `<canvas>` — zero `window.*` listeners,
 * and two-pass dialog closing-before-opening so two modals are never open simultaneously.
 */

import {
  AREA_CATEGORIES_CATALOG,
  CALENDAR_LOOKAHEAD_OPTIONS,
  CALENDAR_WEEK_START_OPTIONS,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_GAMES_ITEMS_TOKENS,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  DEFAULT_TOOLS_ITEMS_TOKENS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  MAX_PINNED_ITEMS,
  MAX_WORLD_CLOCKS,
  NATIVE_DOCK_APP_TOKENS,
  SHORTCUT_LABEL_MAX,
  SHORTCUT_ROUTES_CATALOG,
  TOOLS_ITEMS_CATALOG,
  WORLD_CLOCK_ZONES_CATALOG,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import {
  isKnownMdiIcon,
  MDI_TOTAL_ICON_COUNT,
  normalizeMdiIconSlug,
  ROUTE_PREVIEW_ICONS,
  searchMdiIcons,
  SHORTCUT_DOMAIN_ACTIONS,
  SHORTCUT_DOMAIN_LABELS,
  shortcutActionLabel,
} from "../mdi-catalog.js";
import type { StudioStore } from "../state/store.js";
import type { ConfigurableAppId, DeviceCapabilities, DevicePrefItem, ShortcutItem } from "../types.js";
import { hsvToHex, hsvToRgbJS, isValidHexColor } from "../utils/format.js";
import {
  renderNativeControlRow,
  renderPrefControlRow,
  renderSelectOptions,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "./controls.js";

let cwWheelPainted = false;

interface WorldClockItemView {
  label: string;
  iana: string;
}

const PINNED_UTC_ZONES = new Set([
  "UTC",
  "Etc/UTC",
  "GMT",
  "Etc/GMT",
  "Etc/GMT+0",
  "Etc/GMT-0",
  "Etc/GMT0",
]);
const IANA_ZONE_PATTERN = /^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;
const KNOWN_WORLD_CLOCK_ZONES = new Set(WORLD_CLOCK_ZONES_CATALOG.map((z) => z.iana));
const TEXT_INPUT_DEBOUNCE_MS = 600;

const FALLBACK_CLOCK_FACE_OPTIONS: ReadonlyArray<string> = [
  "Minimal Digital",
  "Modern Analog",
  "Hybrid Digital",
];
const FALLBACK_TIME_FORMAT_OPTIONS: ReadonlyArray<string> = [
  "12-Hour (AM/PM)",
  "24-Hour",
];
const FALLBACK_ALBUM_SORT_OPTIONS: ReadonlyArray<string> = [
  "Alphabetical",
  "Newest on Top",
  "Oldest on Top",
];
const FALLBACK_ARTIST_SORT_OPTIONS: ReadonlyArray<string> = [
  "Oldest on Top",
  "Newest on Top",
  "Alphabetical",
];
const FALLBACK_PODCAST_SORT_OPTIONS: ReadonlyArray<string> = [
  "Newest on Top",
  "Oldest on Top",
];

const APP_MODAL_TITLES: Record<ConfigurableAppId, string> = {
  pinned: "Pinned App",
  home_hub: "Home Hub",
  area: "Area Control",
  music: "Music",
  remote: "Remote Control",
  time: "Time",
  calendar: "Calendar",
  clock: "Clock Face",
  tools: "Tools",
  games: "Games",
};

function isImeSafeEnter(ev: KeyboardEvent): boolean {
  return ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229;
}

function sanitizeClockLabel(raw: unknown, maxBytes = 32): string {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === ";" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const trimmed = collapsed.trim();
  if (typeof TextEncoder === "undefined") {
    return trimmed.slice(0, maxBytes).trimEnd();
  }
  const enc = new TextEncoder();
  if (enc.encode(trimmed).length <= maxBytes) {
    return trimmed;
  }
  let out = "";
  for (const cp of trimmed) {
    if (enc.encode(out + cp).length > maxBytes) break;
    out += cp;
  }
  return out.trimEnd();
}

function fallbackLabelForIana(iana: string): string {
  const tail = iana.split("/").pop() || iana;
  return sanitizeClockLabel(tail.replace(/_/g, " ")) || iana;
}

function parseWorldClocksSpec(raw: unknown): WorldClockItemView[] {
  const out: WorldClockItemView[] = [];
  const seen = new Set<string>();
  for (const part of String(raw ?? "").split(";")) {
    const rec = part.trim();
    if (!rec) continue;
    const pipeIdx = rec.indexOf("|");
    if (pipeIdx < 0) continue;
    const rawLbl = rec.slice(0, pipeIdx);
    const iana = rec.slice(pipeIdx + 1).trim();
    if (!iana || PINNED_UTC_ZONES.has(iana) || !IANA_ZONE_PATTERN.test(iana)) {
      continue;
    }
    const label = sanitizeClockLabel(rawLbl) || fallbackLabelForIana(iana);
    const dedupKey = `${label.toLowerCase()}|${iana}`;
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);
    out.push({ label, iana });
    if (out.length >= MAX_WORLD_CLOCKS) break;
  }
  return out;
}

function serializeWorldClocksSpec(items: ReadonlyArray<WorldClockItemView>): string {
  return items
    .slice(0, MAX_WORLD_CLOCKS)
    .map((item) => {
      const cleaned = sanitizeClockLabel(item.label);
      return cleaned ? `${cleaned}|${item.iana}` : "";
    })
    .filter(Boolean)
    .join(";");
}

function dlgIsToolSupported(token: string, caps: DeviceCapabilities): boolean {
  if (token === "stopwatch" && caps.is_round === false) return false;
  if (token === "level" && caps.has_imu === false) return false;
  return true;
}

function paintHsvColorWheel(canvas: HTMLCanvasElement): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const size = canvas.width;
  const radius = size / 2;
  const img = ctx.createImageData(size, size);
  const data = img.data;
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = x - radius;
      const dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * size + x) * 4;
      if (dist > radius) {
        data[idx + 3] = 0;
        continue;
      }
      const sat = Math.min(1, dist / radius);
      const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
      const [r, g, b] = hsvToRgbJS(angle, sat, 1);
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function pickWheelHexFromEvent(canvas: HTMLCanvasElement, ev: PointerEvent): string | null {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = ev.clientX - rect.left - cx;
  const dy = ev.clientY - rect.top - cy;
  const radius = Math.min(cx, cy);
  const sat = Math.min(1, Math.sqrt(dx * dx + dy * dy) / radius);
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  return hsvToHex(angle, sat, 1);
}

export function syncStudioDialogs(renderRoot: ShadowRoot, store: StudioStore): void {
  const pairs: Array<[string, boolean]> = [
    ["latter-rm-modal", store.removeModal.open],
    ["latter-reset-modal", store.resetModal.open],
    ["latter-add-dev-modal", store.addBleModal.open],
    ["latter-cw-modal", store.colorWheelModal.open],
    ["latter-save-group-modal", store.saveGroupModal?.open ?? false],
    ["latter-app-config-modal", store.appConfigModal?.open ?? false],
    ["latter-shortcut-modal", store.shortcutModal?.open ?? false],
  ];
  // Pass 1: close any open dialog that should now be closed BEFORE opening another modal.
  for (const [id, wantOpen] of pairs) {
    if (wantOpen) continue;
    const dlg = renderRoot.getElementById(id) as HTMLDialogElement | null;
    if (dlg && dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
  }
  // Pass 2: open the active dialog (never > 1 open simultaneously).
  for (const [id, wantOpen] of pairs) {
    if (!wantOpen) continue;
    const dlg = renderRoot.getElementById(id) as HTMLDialogElement | null;
    if (dlg && !dlg.open) {
      try {
        dlg.showModal();
      } catch {
        dlg.setAttribute("open", "");
      }
    }
  }
  if (store.colorWheelModal.open && !cwWheelPainted) {
    const canvas = renderRoot.getElementById("latter-cw-canvas") as HTMLCanvasElement | null;
    if (canvas) {
      paintHsvColorWheel(canvas);
      cwWheelPainted = true;
    }
  } else if (!store.colorWheelModal.open) {
    cwWheelPainted = false;
  }
}

export function renderAppConfigModalBody(store: StudioStore): TemplateResult | typeof nothing {
  const app = store.appConfigModal?.app ?? null;
  if (!app) return nothing;

  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const title = APP_MODAL_TITLES[app] || "Configure App";

  let body: TemplateResult;
  let extraAction: TemplateResult | typeof nothing = nothing;
  let donePrimary = true;

  if (app === "pinned") {
    donePrimary = false;
    const pinnedItems =
      typeof store.getPinnedItems === "function" ? store.getPinnedItems() : [];
    const shortcutEntityMap = new Map(
      (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
    );
    const routeSpecMap = new Map(
      SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]),
    );
    const pinnedPages: Array<{ pageNum: number; startIdx: number; items: ShortcutItem[] }> = [];
    for (let i = 0; i < pinnedItems.length; i += 6) {
      pinnedPages.push({
        pageNum: Math.floor(i / 6) + 1,
        startIdx: i,
        items: pinnedItems.slice(i, i + 6),
      });
    }
    const renderPinnedRow = (item: ShortcutItem, idx: number, total: number): TemplateResult => {
      let displayTitle = item.label;
      let metaLine = "";
      let iconSlug = item.icon;
      if (item.kind === "route") {
        const spec = routeSpecMap.get(item.target);
        if (!displayTitle) {
          displayTitle = spec?.label || item.target;
        }
        metaLine = spec ? `${spec.group} • ${spec.label}` : item.target;
        if (!iconSlug) {
          iconSlug = ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps";
        }
      } else {
        const ent = shortcutEntityMap.get(item.target);
        const dom = item.target.split(".", 1)[0] || "";
        const actLbl = shortcutActionLabel(dom, item.action);
        if (!displayTitle) {
          displayTitle = ent?.name || item.target;
        }
        metaLine = `${actLbl} • ${item.confirm ? "Confirm" : "1-Tap"} • ${item.target}`;
        if (!iconSlug) {
          iconSlug = ent?.icon || "mdi:flash";
        }
      }
      return html`<div class="shortcut-item-row">
        <span class="shortcut-icon-badge" aria-hidden="true">
          <ha-icon .icon=${iconSlug}></ha-icon>
        </span>
        <div class="shortcut-item-info">
          <span class="shortcut-item-title">${displayTitle}</span>
          <span class="shortcut-item-meta">${metaLine}</span>
        </div>
        ${idx > 0
          ? html`<button
              type="button"
              aria-label=${`Move ${displayTitle} up`}
              @click=${() => store.moveShortcutItem("pinned_items", idx, -1)}
              class="btn-icon"
            >
              ↑
            </button>`
          : nothing}
        ${idx < total - 1
          ? html`<button
              type="button"
              aria-label=${`Move ${displayTitle} down`}
              @click=${() => store.moveShortcutItem("pinned_items", idx, 1)}
              class="btn-icon"
            >
              ↓
            </button>`
          : nothing}
        <button
          type="button"
          aria-label=${`Edit ${displayTitle}`}
          @click=${() => store.openShortcutModal("pinned_items", idx)}
          class="btn btn-secondary btn-compact"
        >
          Edit
        </button>
        ${renderTrashIconButton(`Remove ${displayTitle}`, () =>
          store.removeShortcutItem("pinned_items", idx),
        )}
      </div>`;
    };

    body = html`<div class="settings-list">
      ${renderSettingsRow({
        id: "pinned-shortcuts-row",
        label: "Pinned Shortcuts",
        description:
          "Assign Home Assistant entity quick actions or deep-link any Latter app or subpage (6 buttons per page, swipable vertically).",
        stacked: true,
        control: html`<div
          id="pinned-shortcuts-container"
          class="stack"
          role="group"
          aria-label="Pinned App shortcuts"
        >
          ${pinnedPages.length > 0
            ? pinnedPages.map(
                (pg) => html`<div class="shortcut-page-group">
                  <div class="shortcut-page-header">
                    <span>Page ${pg.pageNum}</span>
                    <span>${pg.items.length} of 6 Slots</span>
                  </div>
                  ${pg.items.map((item, localIdx) =>
                    renderPinnedRow(item, pg.startIdx + localIdx, pinnedItems.length),
                  )}
                </div>`,
              )
            : html`<p class="row-description">
                No pinned items configured yet. The Pinned icon stays hidden on the App Dock until you add at least one item.
              </p>`}
          <div class="shortcut-toolbar">
            <button
              type="button"
              id="btn-add-pinned-item"
              ?disabled=${pinnedItems.length >= MAX_PINNED_ITEMS}
              @click=${() => store.openShortcutModal("pinned_items", null)}
              class="btn btn-primary"
            >
              Add Pinned Item
            </button>
          </div>
        </div>`,
      })}
    </div>`;
  } else if (app === "home_hub") {
    const enabledHomeCats =
      typeof store.getEnabledHomeCategories === "function"
        ? store.getEnabledHomeCategories()
        : [...DEFAULT_HOME_CATEGORIES_TOKENS];
    const disabledHomeCats = HOME_CATEGORIES_CATALOG.filter(
      (c) => !enabledHomeCats.includes(c.token),
    );
    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: "Home Categories",
        description:
          "Toggle and reorder categories shown in the Home Hub. The first available category opens by default; categories with no configured entity are not displayed.",
        stacked: true,
        control: html`<div
          id="home-categories-pills"
          class="pill-list"
          role="group"
          aria-label="Home categories"
        >
          ${enabledHomeCats.map((tok, idx) => {
            const meta = HOME_CATEGORIES_CATALOG.find((c) => c.token === tok);
            const lbl = meta ? meta.label : tok;
            return html`<span class="pill enabled">
              ${idx > 0
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} left`}
                    @click=${() => store.moveHomeCategoryToken(tok, -1)}
                    class="pill-move"
                  >
                    ‹
                  </button>`
                : nothing}
              <button
                type="button"
                aria-pressed="true"
                @click=${() => store.toggleHomeCategoryToken(tok)}
                class="pill-toggle"
              >
                ✓ ${lbl}
              </button>
              ${idx < enabledHomeCats.length - 1
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} right`}
                    @click=${() => store.moveHomeCategoryToken(tok, 1)}
                    class="pill-move"
                  >
                    ›
                  </button>`
                : nothing}
            </span>`;
          })}
          ${disabledHomeCats.map(
            (cat) => html`<span class="pill">
              <button
                type="button"
                aria-pressed="false"
                @click=${() => store.toggleHomeCategoryToken(cat.token)}
                class="pill-toggle"
              >
                + ${cat.label}
              </button>
            </span>`,
          )}
        </div>`,
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-whole-home", [
          "card-whole-home",
          "card-cameras-doorbell",
        ]);
      }}
      class="btn btn-text"
    >
      Open Shared Entities
    </button>`;
  } else if (app === "area") {
    const enabledAreaCats =
      typeof store.getEnabledAreaCategories === "function"
        ? store.getEnabledAreaCategories()
        : [...DEFAULT_AREA_CATEGORIES_TOKENS];
    const disabledAreaCats = AREA_CATEGORIES_CATALOG.filter(
      (c) => !enabledAreaCats.includes(c.token),
    );
    const areaExtraItems =
      typeof store.getSectionItems === "function"
        ? store.getSectionItems("area").filter((it) => it.key !== "ble_beacon_mode")
        : [];
    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: "Area Categories",
        description:
          "Toggle and reorder categories shown in the Area screen. The first available category opens by default; categories with no entities in the active Area are not displayed.",
        stacked: true,
        control: html`<div
          id="area-categories-pills"
          class="pill-list"
          role="group"
          aria-label="Area categories"
        >
          ${enabledAreaCats.map((tok, idx) => {
            const meta = AREA_CATEGORIES_CATALOG.find((c) => c.token === tok);
            const lbl = meta ? meta.label : tok;
            return html`<span class="pill enabled">
              ${idx > 0
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} left`}
                    @click=${() => store.moveAreaCategoryToken(tok, -1)}
                    class="pill-move"
                  >
                    ‹
                  </button>`
                : nothing}
              <button
                type="button"
                aria-pressed="true"
                @click=${() => store.toggleAreaCategoryToken(tok)}
                class="pill-toggle"
              >
                ✓ ${lbl}
              </button>
              ${idx < enabledAreaCats.length - 1
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} right`}
                    @click=${() => store.moveAreaCategoryToken(tok, 1)}
                    class="pill-move"
                  >
                    ›
                  </button>`
                : nothing}
            </span>`;
          })}
          ${disabledAreaCats.map(
            (cat) => html`<span class="pill">
              <button
                type="button"
                aria-pressed="false"
                @click=${() => store.toggleAreaCategoryToken(cat.token)}
                class="pill-toggle"
              >
                + ${cat.label}
              </button>
            </span>`,
          )}
        </div>`,
      })}
      ${areaExtraItems.map((it) => renderNativeControlRow(store, it))}
    </div>`;
  } else if (app === "music") {
    const sortPrefs =
      typeof store.getPrefs === "function"
        ? store.getPrefs(["album_sort_order", "artist_album_sort_order", "podcast_sort_order"])
        : [];
    const fallbackSortDefs: ReadonlyArray<{
      key: string;
      label: string;
      options: ReadonlyArray<string>;
      defaultVal: string;
    }> = [
      {
        key: "album_sort_order",
        label: "Album Sort Order",
        options: FALLBACK_ALBUM_SORT_OPTIONS,
        defaultVal: "Alphabetical",
      },
      {
        key: "artist_album_sort_order",
        label: "Artist Album Sort Order",
        options: FALLBACK_ARTIST_SORT_OPTIONS,
        defaultVal: "Oldest on Top",
      },
      {
        key: "podcast_sort_order",
        label: "Podcast Sort Order",
        options: FALLBACK_PODCAST_SORT_OPTIONS,
        defaultVal: "Newest on Top",
      },
    ];
    body = html`<div class="settings-list">
      ${sortPrefs.length > 0
        ? sortPrefs.map((p: DevicePrefItem) => renderPrefControlRow(store, p))
        : fallbackSortDefs.map((def) =>
            renderSelectRow({
              label: def.label,
              value: String(cfg[def.key] ?? def.defaultVal),
              rawOptions: def.options.map((o) => ({ value: o, label: o })),
              onChange: (val) => store.stageDeviceSetting(def.key, val),
            }),
          )}
    </div>`;
  } else if (app === "remote") {
    const remoteGroups = data?.system_config?.remote_groups || [];
    const curDevEntry = (data?.system_devices || []).find(
      (d) => d.subentry_id === store.activeSubentryId,
    );
    const curRemoteMode =
      String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
      "area_auto";
    const remoteModeOptions: Array<{ value: string; label: string }> = [
      { value: "area_auto", label: "Follow the active Area" },
      ...remoteGroups.map((g) => ({
        value: `group:${g.id}`,
        label: `Group: ${g.name}`,
      })),
      { value: "all", label: "All System remotes" },
    ];
    if (!remoteModeOptions.some((o) => o.value === curRemoteMode)) {
      const rawId = curRemoteMode.startsWith("group:") ? curRemoteMode.slice(6) : curRemoteMode;
      remoteModeOptions.push({
        value: curRemoteMode,
        label: `Missing group (${rawId})`,
      });
    }
    const remoteEspItems =
      typeof store.getSectionItems === "function" ? store.getSectionItems("remote") : [];
    body = html`<div class="settings-list">
      ${renderSelectRow({
        id: "cfg-device_remote_group",
        label: "Remote Control Group",
        description: "Choose which remotes appear on this Device's Remote screen.",
        value: curRemoteMode,
        rawOptions: remoteModeOptions,
        onChange: (val) =>
          store.stageDeviceSetting("device_remote_group", val, "cfg-device_remote_group"),
      })}
      ${remoteEspItems.map((it) => renderNativeControlRow(store, it))}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.closeAppConfigModal();
        store.openSystemSection("remotes", "card-remote-groups");
      }}
      class="btn btn-text"
    >
      Manage Remote Groups
    </button>`;
  } else if (app === "time") {
    donePrimary = false;
    const localClockLabelPref =
      typeof store.getPref === "function" ? store.getPref("local_clock_label") : undefined;
    const localClockLabelValue = sanitizeClockLabel(
      localClockLabelPref?.value ?? cfg.local_clock_label ?? "",
    );
    const showUtcClockPref =
      typeof store.getPref === "function" ? store.getPref("show_utc_clock") : undefined;
    const showUtcClock = showUtcClockPref
      ? Boolean(showUtcClockPref.value)
      : Boolean(cfg.show_utc_clock);
    const worldClocksPref =
      typeof store.getPref === "function" ? store.getPref("world_clocks") : undefined;
    const enabledWorldClocks = parseWorldClocksSpec(
      worldClocksPref?.value ?? cfg.world_clocks ?? "",
    );
    const atWorldClockLimit = enabledWorldClocks.length >= MAX_WORLD_CLOCKS;

    const renderWorldClockZoneOptions = (selectedIana: string): TemplateResult => {
      const missingSelected =
        selectedIana && !KNOWN_WORLD_CLOCK_ZONES.has(selectedIana)
          ? html`<option value=${selectedIana} selected>${selectedIana}</option>`
          : nothing;
      return html`${missingSelected}${WORLD_CLOCK_ZONES_CATALOG.map(
        (z) =>
          html`<option value=${z.iana} ?selected=${z.iana === selectedIana}>${z.label}</option>`,
      )}`;
    };

    const updateWorldClocks = (
      nextItems: WorldClockItemView[],
      focusId?: string,
      debounceMs?: number,
    ): void => {
      store.stageDeviceSetting(
        "world_clocks",
        serializeWorldClocksSpec(nextItems),
        focusId,
        debounceMs,
      );
    };

    const updateWorldClockItem = (
      idx: number,
      patch: Partial<WorldClockItemView>,
      focusId?: string,
      debounceMs?: number,
    ): void => {
      if (idx < 0 || idx >= enabledWorldClocks.length) return;
      const prev = enabledWorldClocks[idx];
      const nextIana = (patch.iana ?? prev.iana).trim();
      if (!nextIana || PINNED_UTC_ZONES.has(nextIana) || !IANA_ZONE_PATTERN.test(nextIana)) {
        return;
      }
      const nextLabel =
        patch.label !== undefined ? sanitizeClockLabel(patch.label) : prev.label;
      if (!nextLabel) return;
      const dup = enabledWorldClocks.some(
        (item, i) =>
          i !== idx &&
          item.iana === nextIana &&
          item.label.toLowerCase() === nextLabel.toLowerCase(),
      );
      if (dup) return;
      const next = enabledWorldClocks.map((item, i) =>
        i === idx ? { label: nextLabel, iana: nextIana } : { ...item },
      );
      updateWorldClocks(next, focusId, debounceMs);
    };

    const moveWorldClock = (idx: number, delta: -1 | 1): void => {
      const target = idx + delta;
      if (idx < 0 || target < 0 || target >= enabledWorldClocks.length) return;
      const next = [...enabledWorldClocks];
      const [picked] = next.splice(idx, 1);
      next.splice(target, 0, picked);
      updateWorldClocks(next);
    };

    const removeWorldClock = (idx: number): void => {
      updateWorldClocks(enabledWorldClocks.filter((_, i) => i !== idx));
    };

    const getRenderRoot = (): ShadowRoot | null =>
      (store.host as unknown as { renderRoot?: ShadowRoot })?.renderRoot ?? null;

    const onAddWorldClock = (): void => {
      if (atWorldClockLimit) return;
      const root = getRenderRoot();
      const newLabelEl = root?.getElementById(
        "cfg-world_clock_new_label",
      ) as HTMLInputElement | null;
      const zoneSelEl = root?.getElementById(
        "cfg-world_clocks_add",
      ) as HTMLSelectElement | null;
      const typedLabel = sanitizeClockLabel(newLabelEl?.value ?? store.worldClockNewLabel);
      const picked = (zoneSelEl?.value ?? store.worldClockNewZone).trim();
      if (!typedLabel) {
        store.showToast("Enter a city or label for this World Clock", true);
        newLabelEl?.focus();
        return;
      }
      if (!picked || PINNED_UTC_ZONES.has(picked) || !IANA_ZONE_PATTERN.test(picked)) {
        store.showToast("Select a time zone for this World Clock", true);
        zoneSelEl?.focus();
        return;
      }
      const dup = enabledWorldClocks.some(
        (item) =>
          item.iana === picked && item.label.toLowerCase() === typedLabel.toLowerCase(),
      );
      if (dup) {
        store.showToast("That World Clock is already added", true);
        return;
      }
      store.worldClockNewLabel = "";
      store.worldClockNewZone = "";
      if (newLabelEl) newLabelEl.value = "";
      if (zoneSelEl) zoneSelEl.value = "";
      updateWorldClocks(
        [...enabledWorldClocks, { label: typedLabel, iana: picked }],
        "btn-world_clock_add",
      );
    };

    body = html`<div class="settings-list">
      ${renderSettingsRow({
        id: "time-local-clock-label",
        label: "Local Clock Label",
        forId: "cfg-local_clock_label",
        description: "Optional custom label shown above local time on the Clock tab.",
        control: html`<input
          type="text"
          id="cfg-local_clock_label"
          maxlength="32"
          enterkeyhint="done"
          placeholder="Optional label…"
          .value=${localClockLabelValue}
          @input=${(ev: Event) => {
            const cleaned = sanitizeClockLabel((ev.currentTarget as HTMLInputElement).value);
            store.stageDeviceSetting(
              "local_clock_label",
              cleaned,
              "cfg-local_clock_label",
              TEXT_INPUT_DEBOUNCE_MS,
            );
          }}
          @change=${(ev: Event) => {
            const el = ev.currentTarget as HTMLInputElement;
            const cleaned = sanitizeClockLabel(el.value);
            el.value = cleaned;
            store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
          }}
          @keydown=${(ev: KeyboardEvent) => {
            if (!isImeSafeEnter(ev)) return;
            ev.preventDefault();
            const el = ev.currentTarget as HTMLInputElement;
            const cleaned = sanitizeClockLabel(el.value);
            el.value = cleaned;
            store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
            void store.flushAllPendingSettings();
          }}
        />`,
      })}
      ${renderSwitchRow({
        id: "cfg-show_utc_clock",
        label: "Show UTC Clock",
        description: "Pin a live 24-hour UTC reference row to this Device's Clock tab.",
        checked: showUtcClock,
        onChange: (checked) => {
          store.stageDeviceSetting("show_utc_clock", checked, "cfg-show_utc_clock");
        },
      })}
      ${renderSettingsRow({
        id: "time-world-clocks",
        label: "World Clocks",
        description:
          "Configure up to 4 custom-labeled time zones (UTC-12:00 to UTC+14:00) shown on this Device's Clock tab.",
        stacked: true,
        control: html`<div class="stack">
          ${enabledWorldClocks.length
            ? html`<div
                id="world-clocks-list"
                class="stack"
                role="group"
                aria-label="Configured World Clocks"
              >
                ${enabledWorldClocks.map((entry, idx) => {
                  const lblId = `cfg-world_clock_${idx + 1}_label`;
                  const zoneId = `cfg-world_clock_${idx + 1}_zone`;
                  return html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <label for=${lblId}>World Clock ${idx + 1} City Label</label>
                        <input
                          type="text"
                          id=${lblId}
                          maxlength="32"
                          enterkeyhint="done"
                          placeholder="Enter city or label…"
                          .value=${entry.label}
                          @input=${(ev: Event) => {
                            const cleaned = sanitizeClockLabel(
                              (ev.currentTarget as HTMLInputElement).value,
                            );
                            if (cleaned) {
                              updateWorldClockItem(
                                idx,
                                { label: cleaned },
                                lblId,
                                TEXT_INPUT_DEBOUNCE_MS,
                              );
                            }
                          }}
                          @change=${(ev: Event) => {
                            const el = ev.currentTarget as HTMLInputElement;
                            const cleaned = sanitizeClockLabel(el.value);
                            if (!cleaned) {
                              el.value = entry.label;
                              store.showToast("City label cannot be empty", true);
                              return;
                            }
                            el.value = cleaned;
                            updateWorldClockItem(idx, { label: cleaned }, lblId);
                          }}
                          @keydown=${(ev: KeyboardEvent) => {
                            if (!isImeSafeEnter(ev)) return;
                            ev.preventDefault();
                            const el = ev.currentTarget as HTMLInputElement;
                            const cleaned = sanitizeClockLabel(el.value);
                            if (!cleaned) {
                              el.value = entry.label;
                              store.showToast("City label cannot be empty", true);
                              return;
                            }
                            el.value = cleaned;
                            updateWorldClockItem(idx, { label: cleaned }, lblId);
                            void store.flushAllPendingSettings();
                          }}
                        />
                      </div>
                      <div class="stacked-field">
                        <label for=${zoneId}>World Clock ${idx + 1} Time Zone</label>
                        <select
                          id=${zoneId}
                          .value=${entry.iana}
                          @change=${(ev: Event) =>
                            updateWorldClockItem(
                              idx,
                              { iana: (ev.currentTarget as HTMLSelectElement).value },
                              zoneId,
                            )}
                        >
                          ${renderWorldClockZoneOptions(entry.iana)}
                        </select>
                      </div>
                    </div>
                    ${idx > 0
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${entry.label} up`}
                          @click=${() => moveWorldClock(idx, -1)}
                          class="btn-icon"
                        >
                          ↑
                        </button>`
                      : nothing}
                    ${idx < enabledWorldClocks.length - 1
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${entry.label} down`}
                          @click=${() => moveWorldClock(idx, 1)}
                          class="btn-icon"
                        >
                          ↓
                        </button>`
                      : nothing}
                    ${renderTrashIconButton(
                      `Remove ${entry.label} (${entry.iana})`,
                      () => removeWorldClock(idx),
                    )}
                  </div>`;
                })}
              </div>`
            : nothing}
          <div class="list-row">
            <div class="list-row-main">
              <div class="stacked-field">
                <label for="cfg-world_clock_new_label">New City Label</label>
                <input
                  type="text"
                  id="cfg-world_clock_new_label"
                  maxlength="32"
                  enterkeyhint="done"
                  placeholder="Enter city or label…"
                  ?disabled=${atWorldClockLimit}
                  .value=${store.worldClockNewLabel}
                  @input=${(ev: Event) => {
                    store.worldClockNewLabel = (ev.currentTarget as HTMLInputElement).value;
                    store.host.requestUpdate();
                  }}
                  @keydown=${(ev: KeyboardEvent) => {
                    if (!isImeSafeEnter(ev)) return;
                    ev.preventDefault();
                    onAddWorldClock();
                  }}
                />
              </div>
              <div class="stacked-field">
                <label for="cfg-world_clocks_add">Add Time Zone</label>
                <select
                  id="cfg-world_clocks_add"
                  ?disabled=${atWorldClockLimit}
                  .value=${store.worldClockNewZone}
                  @change=${(ev: Event) => {
                    store.worldClockNewZone = (ev.currentTarget as HTMLSelectElement).value;
                    store.host.requestUpdate();
                  }}
                >
                  <option value="" ?selected=${!store.worldClockNewZone}>
                    ${atWorldClockLimit
                      ? "Maximum 4 World Clocks added"
                      : "Select a time zone (UTC-12 to UTC+14)…"}
                  </option>
                  ${atWorldClockLimit
                    ? nothing
                    : renderWorldClockZoneOptions(store.worldClockNewZone)}
                </select>
              </div>
            </div>
            <button
              type="button"
              id="btn-world_clock_add"
              ?disabled=${atWorldClockLimit}
              @click=${() => onAddWorldClock()}
              class="btn btn-primary"
            >
              Add
            </button>
          </div>
        </div>`,
      })}
    </div>`;
  } else if (app === "clock") {
    const clockPrefs =
      typeof store.getPrefs === "function"
        ? store.getPrefs(["clock_face", "time_format"])
        : [];
    const faceOptions =
      caps.is_round === false
        ? FALLBACK_CLOCK_FACE_OPTIONS.filter((o) => o !== "Modern Analog")
        : FALLBACK_CLOCK_FACE_OPTIONS;
    body = html`<div class="settings-list">
      ${clockPrefs.length > 0
        ? clockPrefs.map((p: DevicePrefItem) => renderPrefControlRow(store, p))
        : html`${renderSelectRow({
              id: "cfg-clock_face",
              label: "Clock Face",
              value: String(cfg.clock_face ?? "Minimal Digital"),
              rawOptions: faceOptions.map((o) => ({ value: o, label: o })),
              onChange: (val) => store.stageDeviceSetting("clock_face", val, "cfg-clock_face"),
            })}
            ${renderSelectRow({
              id: "cfg-time_format",
              label: "Time Format",
              value: String(cfg.time_format ?? "12-Hour (AM/PM)"),
              rawOptions: FALLBACK_TIME_FORMAT_OPTIONS.map((o) => ({ value: o, label: o })),
              onChange: (val) => store.stageDeviceSetting("time_format", val, "cfg-time_format"),
            })}`}
    </div>`;
  } else if (app === "calendar") {
    const lookaheadPref =
      typeof store.getPref === "function" ? store.getPref("calendar_lookahead_days") : undefined;
    const rawLookahead = Number(lookaheadPref?.value ?? cfg.calendar_lookahead_days ?? 30);
    const lookaheadDays =
      rawLookahead <= 10 ? 7 : rawLookahead <= 21 ? 14 : rawLookahead <= 45 ? 30 : 60;

    const weekStartPref =
      typeof store.getPref === "function" ? store.getPref("calendar_week_start") : undefined;
    const weekStartOptions = (
      weekStartPref?.options && weekStartPref.options.length > 0
        ? weekStartPref.options
        : CALENDAR_WEEK_START_OPTIONS
    ).map((opt) => ({ value: opt, label: opt }));
    const weekStartVal = String(weekStartPref?.value ?? cfg.calendar_week_start ?? "Sunday");

    body = html`<div class="settings-list">
      ${renderSelectRow({
        id: "cfg-calendar_lookahead_days",
        label: "Overview Lookahead",
        description:
          "Number of upcoming days shown on the Overview tab (days with no events are omitted).",
        value: String(lookaheadDays),
        rawOptions: CALENDAR_LOOKAHEAD_OPTIONS.map((o) => ({
          value: String(o.value),
          label: o.label,
        })),
        onChange: (val) =>
          store.stageDeviceSetting(
            "calendar_lookahead_days",
            Number(val),
            "cfg-calendar_lookahead_days",
          ),
      })}
      ${renderSelectRow({
        id: "cfg-calendar_week_start",
        label: "Start Week On",
        description: "First column shown in Week and Month views.",
        value: weekStartVal,
        rawOptions: weekStartOptions,
        onChange: (val) =>
          store.stageDeviceSetting("calendar_week_start", val, "cfg-calendar_week_start"),
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-calendars");
      }}
      class="btn btn-text"
    >
      Open Shared Entities
    </button>`;
  } else if (app === "tools") {
    const visibleCatalog = TOOLS_ITEMS_CATALOG.filter((c) => dlgIsToolSupported(c.token, caps));
    const visibleSet = new Set(visibleCatalog.map((c) => c.token));
    const enabledTools = (
      typeof store.getEnabledToolsItems === "function"
        ? store.getEnabledToolsItems()
        : [...DEFAULT_TOOLS_ITEMS_TOKENS]
    ).filter((tok) => visibleSet.has(tok));
    const disabledTools = visibleCatalog.filter((c) => !enabledTools.includes(c.token));

    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: "Tools",
        description: "Toggle and reorder utilities shown in the Tools launcher.",
        stacked: true,
        control: html`<div
          id="tools-items-pills"
          class="pill-list"
          role="group"
          aria-label="Tools"
        >
          ${enabledTools.map((tok, idx) => {
            const meta = visibleCatalog.find((c) => c.token === tok);
            const lbl = meta ? meta.label : tok;
            return html`<span class="pill enabled">
              ${idx > 0
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} left`}
                    @click=${() => store.moveToolItemToken(tok, -1)}
                    class="pill-move"
                  >
                    ‹
                  </button>`
                : nothing}
              <button
                type="button"
                aria-pressed="true"
                @click=${() => store.toggleToolItemToken(tok)}
                class="pill-toggle"
              >
                ✓ ${lbl}
              </button>
              ${idx < enabledTools.length - 1
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} right`}
                    @click=${() => store.moveToolItemToken(tok, 1)}
                    class="pill-move"
                  >
                    ›
                  </button>`
                : nothing}
            </span>`;
          })}
          ${disabledTools.map(
            (cat) => html`<span class="pill">
              <button
                type="button"
                aria-pressed="false"
                @click=${() => store.toggleToolItemToken(cat.token)}
                class="pill-toggle"
              >
                + ${cat.label}
              </button>
            </span>`,
          )}
        </div>`,
      })}
    </div>`;
  } else {
    const enabledGames =
      typeof store.getEnabledGamesItems === "function"
        ? store.getEnabledGamesItems()
        : [...DEFAULT_GAMES_ITEMS_TOKENS];
    const disabledGames = GAMES_ITEMS_CATALOG.filter((c) => !enabledGames.includes(c.token));

    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: "Games",
        description: "Toggle and reorder games shown in the Games launcher.",
        stacked: true,
        control: html`<div
          id="games-items-pills"
          class="pill-list"
          role="group"
          aria-label="Games"
        >
          ${enabledGames.map((tok, idx) => {
            const meta = GAMES_ITEMS_CATALOG.find((c) => c.token === tok);
            const lbl = meta ? meta.label : tok;
            return html`<span class="pill enabled">
              ${idx > 0
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} left`}
                    @click=${() => store.moveGameItemToken(tok, -1)}
                    class="pill-move"
                  >
                    ‹
                  </button>`
                : nothing}
              <button
                type="button"
                aria-pressed="true"
                @click=${() => store.toggleGameItemToken(tok)}
                class="pill-toggle"
              >
                ✓ ${lbl}
              </button>
              ${idx < enabledGames.length - 1
                ? html`<button
                    type="button"
                    aria-label=${`Move ${lbl} right`}
                    @click=${() => store.moveGameItemToken(tok, 1)}
                    class="pill-move"
                  >
                    ›
                  </button>`
                : nothing}
            </span>`;
          })}
          ${disabledGames.map(
            (cat) => html`<span class="pill">
              <button
                type="button"
                aria-pressed="false"
                @click=${() => store.toggleGameItemToken(cat.token)}
                class="pill-toggle"
              >
                + ${cat.label}
              </button>
            </span>`,
          )}
        </div>`,
      })}
    </div>`;
  }

  return html`<div class="dialog-body">
    <h3 id="latter-app-config-title" class="dialog-title">${title}</h3>
    ${body}
    <div class="dialog-actions">
      ${extraAction}
      <button
        type="button"
        id="app-config-done-btn"
        @click=${() => store.closeAppConfigModal()}
        class="btn ${donePrimary ? "btn-primary" : "btn-secondary"}"
      >
        Done
      </button>
    </div>
  </div>`;
}

export function renderStudioDialogs(store: StudioStore): TemplateResult {
  const persons = store.state?.catalog?.persons || [];
  const candidates = store.state?.discovered_ble_devices || [];

  const onBackdropClick = (ev: Event, closeFn: () => void): void => {
    if (ev.target === ev.currentTarget) {
      closeFn();
    }
  };

  const onCwPointerDown = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    canvas.setPointerCapture?.(pev.pointerId);
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerMove = (ev: Event): void => {
    const pev = ev as PointerEvent;
    if (pev.buttons === 0) return;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerUp = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    if (canvas.hasPointerCapture?.(pev.pointerId)) {
      canvas.releasePointerCapture(pev.pointerId);
    }
  };

  const onCwHexInput = (ev: Event): void => {
    const raw = (ev.currentTarget as HTMLInputElement).value;
    store.colorWheelModal = { ...store.colorWheelModal, hex: raw.toUpperCase() };
    store.host.requestUpdate();
  };

  const onCwNameInput = (ev: Event): void => {
    store.colorWheelModal = {
      ...store.colorWheelModal,
      name: (ev.currentTarget as HTMLInputElement).value,
    };
  };

  const cwValidHex = isValidHexColor(store.colorWheelModal.hex)
    ? store.colorWheelModal.hex
    : "";

  const scModal = store.shortcutModal;
  const scIsDock = scModal.listKey === "dock_items";
  const scTitle =
    scModal.editIndex !== null
      ? scIsDock
        ? "Edit Custom Dock Shortcut"
        : "Edit Pinned Shortcut"
      : scIsDock
        ? "Add Custom Dock Shortcut"
        : "Add Pinned Shortcut";
  const devCaps = store.state?.capabilities || {};
  const availableRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!scIsDock && r.dockOnly) return false;
    if (scIsDock && (r.token === "settings:root" || NATIVE_DOCK_APP_TOKENS.includes(r.token))) {
      return false;
    }
    if (r.capability === "round" && devCaps.is_round === false) return false;
    if (r.capability === "imu" && devCaps.has_imu === false) return false;
    return true;
  });
  const routeGroups: Array<{ group: string; items: typeof availableRoutes }> = [];
  for (const r of availableRoutes) {
    const grpName = r.group || "Apps";
    const existingGrp = routeGroups.find((g) => g.group === grpName);
    if (existingGrp) {
      existingGrp.items.push(r);
    } else {
      routeGroups.push({ group: grpName, items: [r] });
    }
  }

  const allShortcutEntities = store.state?.catalog?.shortcut_entities || [];
  const availableDomains = Array.from(
    new Set(allShortcutEntities.map((e) => e.domain)),
  ).sort();
  const scSearchLower = scModal.entitySearch.trim().toLowerCase();
  const filteredShortcutEntities = allShortcutEntities.filter((e) => {
    if (scModal.entityDomainFilter !== "all" && e.domain !== scModal.entityDomainFilter) {
      return false;
    }
    if (!scSearchLower) return true;
    return (
      e.name.toLowerCase().includes(scSearchLower) ||
      e.id.toLowerCase().includes(scSearchLower) ||
      e.area_name.toLowerCase().includes(scSearchLower)
    );
  });
  const selectedEntityObj =
    allShortcutEntities.find((e) => e.id === scModal.entityTarget) || null;
  const selectedEntityDomain = selectedEntityObj
    ? selectedEntityObj.domain
    : (scModal.entityTarget.split(".", 1)[0] || "");
  const availableEntityActions = SHORTCUT_DOMAIN_ACTIONS[selectedEntityDomain] || [];
  const effectiveRouteTarget = availableRoutes.some((r) => r.token === scModal.routeTarget)
    ? scModal.routeTarget
    : (availableRoutes[0]?.token || scModal.routeTarget);
  const selectedRouteSpec =
    availableRoutes.find((r) => r.token === effectiveRouteTarget) ||
    SHORTCUT_ROUTES_CATALOG.find((r) => r.token === effectiveRouteTarget);
  const autoDefaultLabel =
    scModal.kind === "route"
      ? selectedRouteSpec?.label || "Shortcut"
      : selectedEntityObj?.name || scModal.entityTarget || "Entity Action";
  const autoDefaultIcon =
    scModal.kind === "route"
      ? ROUTE_PREVIEW_ICONS[effectiveRouteTarget] || "mdi:apps"
      : selectedEntityObj?.icon || "mdi:flash";
  const selectedCustomIcon = normalizeMdiIconSlug(scModal.icon);
  const typedSearchIcon = normalizeMdiIconSlug(scModal.iconSearch);
  const previewIcon =
    selectedCustomIcon ||
    (isKnownMdiIcon(typedSearchIcon) ? typedSearchIcon : autoDefaultIcon);
  const hasIconQuery = scModal.iconSearch.trim().length > 0;
  const { items: filteredMdiIcons, totalMatches: mdiMatchCount } = searchMdiIcons(
    scModal.iconSearch,
    120,
  );

  return html`
    <dialog
      id="latter-rm-modal"
      aria-labelledby="latter-rm-title"
      @cancel=${() => store.closeRemoveDeviceModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeRemoveDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-rm-title" class="dialog-title">Remove Device From Latter?</h3>
        <p class="dialog-text">
          Removes "${store.removeModal.title || "Device"}" from Latter. Your ESPHome device stays in Home Assistant.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeRemoveDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.removeModal.busy}
            @click=${() => void store.confirmRemoveDevice()}
            class="btn btn-danger-filled"
          >
            Remove Device
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-reset-modal"
      aria-labelledby="latter-reset-title"
      @cancel=${() => store.closeResetDeviceModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeResetDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-reset-title" class="dialog-title">Reset to Defaults?</h3>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "latter-reset-device-settings",
            label: "Settings Saved on the Device",
            description: "Erases everything saved on the Device; it restarts.",
            checked: store.resetModal.deviceSettings,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, deviceSettings: checked };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "latter-reset-latter-options",
            label: "Latter Settings for This Device",
            checked: store.resetModal.latterOptions,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, latterOptions: checked };
              store.host.requestUpdate();
            },
          })}
        </div>
        <p class="dialog-text">
          Wi-Fi and pairing are kept, so the Device rejoins Home Assistant by itself. Its ESPHome binding and Music Assistant player link are kept too.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeResetDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-reset-confirm-btn"
            ?disabled=${store.resetModal.busy || (!store.resetModal.deviceSettings && !store.resetModal.latterOptions)}
            @click=${() => void store.confirmResetDevice()}
            class="btn btn-danger-filled"
          >
            Reset
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-add-dev-modal"
      aria-labelledby="latter-add-dev-title"
      @cancel=${() => store.closeAddBleModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeAddBleModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-add-dev-title" class="dialog-title">Add a BLE Tag</h3>
        <p class="dialog-text">
          A phone, watch or Bluetooth tag that Latter tracks by Area. Latter Devices are added in Home Assistant.
        </p>
        <div class="stacked-field">
          <label for="ble-candidate-picker">Discovered Bluetooth Devices</label>
          <select
            id="ble-candidate-picker"
            .value=${store.addBleModal.candidateAddr}
            @change=${(ev: Event) =>
              store.selectBleCandidateInModal((ev.currentTarget as HTMLSelectElement).value)}
          >
            <option value="">Enter manually…</option>
            ${candidates.map((c) => {
              const addr = c.target_address || c.address || "";
              const lbl =
                c.label ||
                `${c.title || c.name || addr}${c.area_name ? ` (${c.area_name})` : ""}`;
              return html`<option value=${addr} ?selected=${addr === store.addBleModal.candidateAddr}>
                ${lbl}
              </option>`;
            })}
          </select>
        </div>
        <div class="stacked-field">
          <label for="ble-custom-name">Name</label>
          <input
            type="text"
            id="ble-custom-name"
            placeholder="e.g. phone, watch, keys"
            .value=${store.addBleModal.name}
            @input=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                name: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <label for="ble-custom-addr">Target Address or Entity</label>
          <input
            type="text"
            id="ble-custom-addr"
            placeholder="AA:BB:CC:DD:EE:FF, iBeacon UUID, or tracker entity"
            .value=${store.addBleModal.address}
            @input=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                address: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
            class="mono"
          />
          <span class="help-text">
            Enter a static BLE MAC address, iBeacon UUID (with optional major:minor), or Home Assistant Companion App or tracker entity.
          </span>
        </div>
        <div class="stacked-field">
          <label for="ble-custom-person">Assigned Person (Optional)</label>
          <select
            id="ble-custom-person"
            .value=${store.addBleModal.assignedPerson}
            @change=${(ev: Event) => {
              store.addBleModal = {
                ...store.addBleModal,
                assignedPerson: (ev.currentTarget as HTMLSelectElement).value,
              };
            }}
          >
            ${renderSelectOptions(persons, store.addBleModal.assignedPerson, "Unassigned")}
          </select>
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeAddBleModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.addBleModal.busy}
            @click=${() => void store.confirmAddBleModal()}
            class="btn btn-primary"
          >
            Add BLE Tag
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-cw-modal"
      aria-labelledby="latter-cw-title"
      @cancel=${() => store.closeColorWheelModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeColorWheelModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-cw-title" class="dialog-title">Add a Custom Color</h3>
        <div class="color-wheel" aria-hidden="true">
          <canvas
            id="latter-cw-canvas"
            width="220"
            height="220"
            @pointerdown=${onCwPointerDown}
            @pointermove=${onCwPointerMove}
            @pointerup=${onCwPointerUp}
          ></canvas>
        </div>
        <div class="color-hex-row">
          <input
            type="color"
            id="latter-cw-native"
            aria-label="Color"
            .value=${cwValidHex}
            @input=${onCwHexInput}
          />
          <input
            type="text"
            id="latter-cw-hex"
            aria-label="Hex color"
            placeholder="#RRGGBB"
            maxlength="7"
            .value=${store.colorWheelModal.hex}
            @input=${onCwHexInput}
          />
        </div>
        <div class="stacked-field">
          <label for="latter-cw-name">Name</label>
          <input
            type="text"
            id="latter-cw-name"
            placeholder="e.g. Sunset Coral"
            .value=${store.colorWheelModal.name}
            @input=${onCwNameInput}
          />
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeColorWheelModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            @click=${() => void store.saveColorWheelSelection()}
            class="btn btn-primary"
          >
            Save Color
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-save-group-modal"
      aria-labelledby="latter-save-group-title"
      @cancel=${() => store.closeSaveGroupModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeSaveGroupModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-save-group-title" class="dialog-title">Save Custom Group</h3>
        <p class="dialog-text">
          Saves this Device's settings as a reusable Device Group and assigns this Device to it.
        </p>
        <div class="stacked-field">
          <label for="save-group-name">Group Name</label>
          <input
            type="text"
            id="save-group-name"
            placeholder="e.g. Nightstands, Guest Suites"
            .value=${store.saveGroupModal?.name || ""}
            @input=${(ev: Event) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                name: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <label for="save-group-desc">Description (Optional)</label>
          <input
            type="text"
            id="save-group-desc"
            placeholder="Optional summary of these settings"
            .value=${store.saveGroupModal?.description || ""}
            @input=${(ev: Event) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                description: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "save-group-include-display",
            label: "Include Display Settings",
            description: "Sync wallpapers, clock face, color profile, and media styling.",
            checked: Boolean(store.saveGroupModal?.includeDisplay),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeDisplay: checked,
              };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "save-group-include-interface",
            label: "Include Interface & Shortcuts",
            description: "Sync start screen, App Dock, pinned shortcuts, and hub categories.",
            checked: Boolean(store.saveGroupModal?.includeInterface),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeInterface: checked,
              };
              store.host.requestUpdate();
            },
          })}
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeSaveGroupModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-save-group-confirm-btn"
            ?disabled=${Boolean(store.saveGroupModal?.busy)}
            @click=${() => void store.confirmSaveGroupModal()}
            class="btn btn-primary"
          >
            Save Group
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-app-config-modal"
      aria-labelledby="latter-app-config-title"
      @cancel=${() => store.closeAppConfigModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeAppConfigModal())}
      class="studio-dialog shortcut-dialog"
    >
      ${renderAppConfigModalBody(store)}
    </dialog>

    <dialog
      id="latter-shortcut-modal"
      aria-labelledby="latter-shortcut-title"
      @cancel=${() => store.closeShortcutModal()}
      @click=${(ev: Event) => onBackdropClick(ev, () => store.closeShortcutModal())}
      class="studio-dialog shortcut-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-shortcut-title" class="dialog-title">${scTitle}</h3>
        <div class="scope-tabs" role="tablist" aria-label="Shortcut Type">
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "route")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "route" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "route" ? "active" : ""}"
          >
            ${scIsDock ? "Subpage" : "App or Page"}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "entity")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "entity" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "entity" ? "active" : ""}"
          >
            Home Assistant Entity
          </button>
        </div>

        ${scModal.kind === "route"
          ? html`<div class="stacked-field">
              <label for="shortcut-route-select">
                ${scIsDock ? "Target Subpage" : "Target App or Subpage"}
              </label>
              <select
                id="shortcut-route-select"
                .value=${effectiveRouteTarget}
                @change=${(ev: Event) => {
                  const val = (ev.currentTarget as HTMLSelectElement).value;
                  store.shortcutModal = { ...store.shortcutModal, routeTarget: val };
                  store.host.requestUpdate();
                }}
              >
                ${routeGroups.map(
                  (grp) => html`<optgroup label=${grp.group}>
                    ${grp.items.map(
                      (item) => html`<option
                        value=${item.token}
                        ?selected=${item.token === effectiveRouteTarget}
                      >
                        ${item.label}
                      </option>`,
                    )}
                  </optgroup>`,
                )}
              </select>
            </div>`
          : html`<div class="list-row-main">
                <div class="stacked-field">
                  <label for="shortcut-domain-filter">Domain Filter</label>
                  <select
                    id="shortcut-domain-filter"
                    .value=${scModal.entityDomainFilter}
                    @change=${(ev: Event) => {
                      const nextDom = (ev.currentTarget as HTMLSelectElement).value;
                      const nextList = allShortcutEntities.filter(
                        (e) => nextDom === "all" || e.domain === nextDom,
                      );
                      const keepEnt = nextList.some((e) => e.id === scModal.entityTarget)
                        ? scModal.entityTarget
                        : (nextList[0]?.id || "");
                      const effDom = keepEnt.split(".", 1)[0] || nextDom;
                      const nextAct = SHORTCUT_DOMAIN_ACTIONS[effDom]?.[0]?.action || "";
                      store.shortcutModal = {
                        ...store.shortcutModal,
                        entityDomainFilter: nextDom,
                        entityTarget: keepEnt,
                        action: nextAct,
                      };
                      store.host.requestUpdate();
                    }}
                  >
                    <option value="all" ?selected=${scModal.entityDomainFilter === "all"}>
                      All Domains
                    </option>
                    ${availableDomains.map(
                      (dom) => html`<option
                        value=${dom}
                        ?selected=${dom === scModal.entityDomainFilter}
                      >
                        ${SHORTCUT_DOMAIN_LABELS[dom] || dom}
                      </option>`,
                    )}
                  </select>
                </div>
                <div class="stacked-field">
                  <label for="shortcut-entity-search">Filter Entities</label>
                  <input
                    type="search"
                    id="shortcut-entity-search"
                    placeholder="Search name, Area, or entity ID…"
                    .value=${scModal.entitySearch}
                    @input=${(ev: Event) => {
                      const query = (ev.currentTarget as HTMLInputElement).value;
                      const qLow = query.trim().toLowerCase();
                      const matches = allShortcutEntities.filter((e) => {
                        if (
                          scModal.entityDomainFilter !== "all" &&
                          e.domain !== scModal.entityDomainFilter
                        ) {
                          return false;
                        }
                        if (!qLow) return true;
                        return (
                          e.name.toLowerCase().includes(qLow) ||
                          e.id.toLowerCase().includes(qLow) ||
                          e.area_name.toLowerCase().includes(qLow)
                        );
                      });
                      const nextTarget = matches.some((e) => e.id === scModal.entityTarget)
                        ? scModal.entityTarget
                        : (matches[0]?.id || scModal.entityTarget);
                      const nextDom = nextTarget.split(".", 1)[0] || "";
                      const validActs = SHORTCUT_DOMAIN_ACTIONS[nextDom] || [];
                      const nextAct = validActs.some((a) => a.action === scModal.action)
                        ? scModal.action
                        : (validActs[0]?.action || scModal.action);
                      store.shortcutModal = {
                        ...store.shortcutModal,
                        entitySearch: query,
                        entityTarget: nextTarget,
                        action: nextAct,
                      };
                      store.host.requestUpdate();
                    }}
                  />
                </div>
              </div>
              <div class="stacked-field">
                <label for="shortcut-entity-select">Entity</label>
                <select
                  id="shortcut-entity-select"
                  .value=${scModal.entityTarget}
                  @change=${(ev: Event) => {
                    const nextEnt = (ev.currentTarget as HTMLSelectElement).value;
                    const dom = nextEnt.split(".", 1)[0] || "";
                    const acts = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
                    const nextAct = acts.some((a) => a.action === scModal.action)
                      ? scModal.action
                      : (acts[0]?.action || "");
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      entityTarget: nextEnt,
                      action: nextAct,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${filteredShortcutEntities.length === 0
                    ? html`<option value="">No matching Home Assistant entities</option>`
                    : filteredShortcutEntities.map(
                        (e) => html`<option
                          value=${e.id}
                          ?selected=${e.id === scModal.entityTarget}
                        >
                          ${e.area_name ? `${e.area_name} — ` : ""}${e.name} (${e.id})
                        </option>`,
                      )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="shortcut-action-select">Action</label>
                <select
                  id="shortcut-action-select"
                  .value=${scModal.action}
                  @change=${(ev: Event) => {
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      action: (ev.currentTarget as HTMLSelectElement).value,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${availableEntityActions.map(
                    (act) => html`<option
                      value=${act.action}
                      ?selected=${act.action === scModal.action}
                    >
                      ${act.label}
                    </option>`,
                  )}
                </select>
              </div>
              ${renderSwitchRow({
                id: "shortcut-confirm-switch",
                label: "Confirm Before Running",
                description: scIsDock
                  ? "Shows a confirmation prompt before running this action from the App Dock."
                  : "Require a confirmation tap instead of running immediately on a single tap.",
                checked: scModal.confirm,
                onChange: (checked) => {
                  store.shortcutModal = { ...store.shortcutModal, confirm: checked };
                  store.host.requestUpdate();
                },
              })}`}

        <div class="stacked-field">
          <label for="shortcut-label-input">Custom Label (Optional)</label>
          <input
            type="text"
            id="shortcut-label-input"
            maxlength=${String(SHORTCUT_LABEL_MAX)}
            placeholder=${autoDefaultLabel}
            .value=${scModal.label}
            @input=${(ev: Event) => {
              store.shortcutModal = {
                ...store.shortcutModal,
                label: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />
        </div>

        <div class="stacked-field">
          <label for="shortcut-icon-input">Icon (Optional MDI Override)</label>
          <div class="shortcut-icon-row">
            <span class="shortcut-icon-badge" aria-hidden="true">
              <ha-icon .icon=${previewIcon}></ha-icon>
            </span>
            <input
              type="text"
              id="shortcut-icon-input"
              placeholder=${`Search all ${MDI_TOTAL_ICON_COUNT.toLocaleString()} icons (e.g. teddy-bear, baby, lamp)…`}
              .value=${scModal.iconSearch}
              @input=${(ev: Event) => {
                const raw = (ev.currentTarget as HTMLInputElement).value;
                store.shortcutModal = {
                  ...store.shortcutModal,
                  iconSearch: raw,
                };
                store.host.requestUpdate();
              }}
            />
            ${scModal.icon || scModal.iconSearch
              ? html`<button
                  type="button"
                  @click=${() => {
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      icon: "",
                      iconSearch: "",
                    };
                    store.host.requestUpdate();
                  }}
                  class="btn btn-text btn-compact"
                >
                  Default Icon
                </button>`
              : nothing}
          </div>
          <p class="row-description">
            ${selectedCustomIcon
              ? `Selected: ${selectedCustomIcon}`
              : `Default: ${autoDefaultIcon}`}
            •
            ${hasIconQuery
              ? mdiMatchCount === 0
                ? "No matching icons — try another keyword"
                : mdiMatchCount > filteredMdiIcons.length
                  ? `Showing ${filteredMdiIcons.length} of ${mdiMatchCount.toLocaleString()} matches`
                  : `${mdiMatchCount.toLocaleString()} matching icon${mdiMatchCount === 1 ? "" : "s"}`
              : `Showing popular icons (${MDI_TOTAL_ICON_COUNT.toLocaleString()} searchable)`}
          </p>
          <div class="mdi-picker-grid" role="listbox" aria-label="Material Design Icons">
            ${filteredMdiIcons.map(
              (slug) => html`<button
                type="button"
                title=${slug}
                aria-label=${slug}
                aria-selected=${String(selectedCustomIcon === slug)}
                @click=${() => {
                  store.shortcutModal = {
                    ...store.shortcutModal,
                    icon: slug,
                  };
                  store.host.requestUpdate();
                }}
                class="mdi-picker-btn ${selectedCustomIcon === slug ? "selected" : ""}"
              >
                <ha-icon .icon=${slug}></ha-icon>
              </button>`,
            )}
          </div>
        </div>

        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeShortcutModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="shortcut-save-btn"
            @click=${() => store.saveShortcutModal()}
            class="btn btn-primary"
          >
            Save Shortcut
          </button>
        </div>
      </div>
    </dialog>
  `;
}
