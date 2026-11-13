// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.
// Source: ha-latter/frontend_src/src/ (build via `node ha-latter/frontend_src/build.mjs`).

// --- src/lib/lit.ts ---
/**
 * Lightweight, strictly typed Lit reactive element & `<template>` marker-part engine for Latter Studio.
 * Preserves live DOM nodes (focus, cursor selection, open selects/details/dialogs) across reactive updates.
 */
const nothing = Symbol.for("latter.lit.nothing");
function css(strings, ...values) {
  let out = "";
  for (let i = 0; i < strings.length; i += 1) {
    out += strings[i];
    if (i < values.length) {
      const v = values[i];
      if (v && typeof v === "object" && "styleSheetText" in (v)) {
        out += (v).styleSheetText;
      } else if (v !== undefined && v !== null) {
        out += String(v);
      }
    }
  }
  return { styleSheetText: out };
}
function html(strings, ...values) {
  return { _$litType$: 1, strings, values };
}
function repeat (
  items,
  keyFn,
  templateFn,
) {
  const keys = [];
  const templates = [];
  for (let i = 0; i < items.length; i += 1) {
    keys.push(keyFn(items[i], i));
    templates.push(templateFn(items[i], i));
  }
  return { _$litKeyed$: 1, keys, templates };
}
const TEMPLATE_CACHE = new WeakMap();
function compileTemplate(strings) {
  const cached = TEMPLATE_CACHE.get(strings);
  if (cached) return cached;
  const descriptors = [];
  let markup = "";
  let inTag = false;
  let quoteChar = "";
  let pendingAttrStart = -1;
  let pendingAttrPrefix = "";
  let pendingAttrName = "";
  let pendingAttrStatics = [];
  let pendingAttrParts = [];
  let attrMarkerSeq = 0;
  for (let i = 0; i < strings.length; i += 1) {
    const chunk = strings[i];
    for (let c = 0; c < chunk.length; c += 1) {
      const ch = chunk[c];
      if (!inTag) {
        if (ch === "<" && chunk.slice(c, c + 4) !== "<!--") {
          inTag = true;
          quoteChar = "";
        }
        markup += ch;
      } else if (quoteChar) {
        if (ch === quoteChar) {
          if (pendingAttrStart >= 0) {
            const tail = markup.slice(pendingAttrStart);
            pendingAttrStatics.push(tail);
            markup = markup.slice(0, pendingAttrStart);
            const markerAttr = `data-latter-b${attrMarkerSeq++}`;
            if (pendingAttrPrefix === "@") {
              descriptors.push({
                kind: "event",
                markerAttr,
                eventName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else if (pendingAttrPrefix === ".") {
              descriptors.push({
                kind: "prop",
                markerAttr,
                propName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else if (pendingAttrPrefix === "?") {
              descriptors.push({
                kind: "bool",
                markerAttr,
                attrName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else {
              descriptors.push({
                kind: "attr",
                markerAttr,
                attrName: pendingAttrName,
                statics: pendingAttrStatics,
                partIndices: pendingAttrParts,
              });
            }
            markup += `${markerAttr}=""`;
            pendingAttrStart = -1;
            pendingAttrPrefix = "";
            pendingAttrName = "";
            pendingAttrStatics = [];
            pendingAttrParts = [];
          } else {
            markup += ch;
          }
          quoteChar = "";
        } else {
          markup += ch;
        }
      } else {
        if (ch === '"' || ch === "'") {
          quoteChar = ch;
          markup += ch;
        } else if (ch === ">") {
          inTag = false;
          markup += ch;
        } else {
          markup += ch;
        }
      }
    }
    if (i === strings.length - 1) break;
    if (!inTag) {
      const commentText = `latter-p-${i}`;
      descriptors.push({ kind: "child", commentText, partIndex: i });
      markup += `<!--${commentText}-->`;
    } else if (quoteChar) {
      if (pendingAttrStart < 0) {
        const eqQuoteIdx = markup.lastIndexOf(`=${quoteChar}`);
        let nameStart = eqQuoteIdx - 1;
        while (nameStart >= 0 && /\s/.test(markup[nameStart])) nameStart -= 1;
        const nameEnd = nameStart + 1;
        while (nameStart > 0 && !/[\s<>"'=]/.test(markup[nameStart - 1])) nameStart -= 1;
        const rawAttr = markup.slice(nameStart, nameEnd);
        const firstStatic = markup.slice(eqQuoteIdx + 2);
        markup = markup.slice(0, nameStart);
        const pfx = rawAttr[0] === "@" || rawAttr[0] === "." || rawAttr[0] === "?" ? rawAttr[0] : "";
        pendingAttrPrefix = pfx;
        pendingAttrName = pfx ? rawAttr.slice(1) : rawAttr;
        pendingAttrStatics = [firstStatic];
        pendingAttrParts = [i];
        pendingAttrStart = markup.length;
      } else {
        const midStatic = markup.slice(pendingAttrStart);
        markup = markup.slice(0, pendingAttrStart);
        pendingAttrStatics.push(midStatic);
        pendingAttrParts.push(i);
      }
    } else {
      const mUnquoted = /([@.?]?[A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*$/.exec(markup);
      if (!mUnquoted) {
        throw new Error(`Unsupported template expression inside tag near: ${markup.slice(-40)}`);
      }
      const rawAttr = mUnquoted[1];
      markup = markup.slice(0, mUnquoted.index);
      const pfx = rawAttr[0] === "@" || rawAttr[0] === "." || rawAttr[0] === "?" ? rawAttr[0] : "";
      const name = pfx ? rawAttr.slice(1) : rawAttr;
      const markerAttr = `data-latter-b${attrMarkerSeq++}`;
      if (pfx === "@") {
        descriptors.push({ kind: "event", markerAttr, eventName: name, partIndex: i });
      } else if (pfx === ".") {
        descriptors.push({ kind: "prop", markerAttr, propName: name, partIndex: i });
      } else if (pfx === "?") {
        descriptors.push({ kind: "bool", markerAttr, attrName: name, partIndex: i });
      } else {
        descriptors.push({
          kind: "attr",
          markerAttr,
          attrName: name,
          statics: ["", ""],
          partIndices: [i],
        });
      }
      markup += `${markerAttr}=""`;
    }
  }
  const templateEl = document.createElement("template");
  templateEl.innerHTML = markup;
  const compiled = { templateEl, descriptors };
  TEMPLATE_CACHE.set(strings, compiled);
  return compiled;
}
class EventPart {
           priority = 1;
          handler = null;
          bound = false;
                   wrapper = (ev) => {
    if (typeof this.handler === "function") {
      this.handler(ev);
    }
  };
                   el;
                   eventName;
                   partIndex;
  constructor(el, eventName, partIndex) {
    this.el = el;
    this.eventName = eventName;
    this.partIndex = partIndex;
  }
  update(values) {
    const next = values[this.partIndex];
    this.handler = typeof next === "function" ? (next) : null;
    if (this.handler && !this.bound) {
      this.el.addEventListener(this.eventName, this.wrapper);
      this.bound = true;
    } else if (!this.handler && this.bound) {
      this.el.removeEventListener(this.eventName, this.wrapper);
      this.bound = false;
    }
  }
}
class BoolAttrPart {
           priority = 1;
          prev = undefined;
                   el;
                   attrName;
                   partIndex;
  constructor(el, attrName, partIndex) {
    this.el = el;
    this.attrName = attrName;
    this.partIndex = partIndex;
  }
  update(values) {
    const next = Boolean(values[this.partIndex] && values[this.partIndex] !== nothing);
    if (next !== this.prev) {
      this.prev = next;
      this.el.toggleAttribute(this.attrName, next);
    }
  }
}
class AttrPart {
           priority = 1;
          prev = undefined;
                   el;
                   attrName;
                   statics;
                   partIndices;
  constructor(el, attrName, statics, partIndices) {
    this.el = el;
    this.attrName = attrName;
    this.statics = statics;
    this.partIndices = partIndices;
  }
  update(values) {
    if (
      this.partIndices.length === 1 &&
      this.statics[0] === "" &&
      this.statics[1] === ""
    ) {
      const raw = values[this.partIndices[0]];
      if (this.attrName.startsWith("aria-") && typeof raw === "boolean") {
        const str = raw ? "true" : "false";
        if (str !== this.prev) {
          this.prev = str;
          this.el.setAttribute(this.attrName, str);
        }
        return;
      }
      if (raw === nothing || raw === null || raw === undefined || raw === false) {
        if (this.prev !== nothing) {
          this.prev = nothing;
          this.el.removeAttribute(this.attrName);
        }
        return;
      }
      const str = String(raw);
      if (str !== this.prev) {
        this.prev = str;
        this.el.setAttribute(this.attrName, str);
      }
      return;
    }
    let out = this.statics[0];
    for (let i = 0; i < this.partIndices.length; i += 1) {
      const v = values[this.partIndices[i]];
      out += v === nothing || v === null || v === undefined ? "" : String(v);
      out += this.statics[i + 1];
    }
    if (out !== this.prev) {
      this.prev = out;
      this.el.setAttribute(this.attrName, out);
    }
  }
}
class PropertyPart {
  // Priority 2 runs AFTER ChildPart (priority 0) so <select> options exist before `.value` is assigned.
           priority = 2;
                   el;
                   propName;
                   partIndex;
  constructor(el, propName, partIndex) {
    this.el = el;
    this.propName = propName;
    this.partIndex = partIndex;
  }
  update(values) {
    const raw = values[this.partIndex];
    const next = raw === nothing || raw === null || raw === undefined ? "" : raw;
    const target = this.el;
    if (target[this.propName] !== next) {
      target[this.propName] = next;
    }
  }
}
function isTemplateResult(v) {
  return Boolean(v && typeof v === "object" && (v)._$litType$ === 1);
}
function isKeyedResult(v) {
  return Boolean(v && typeof v === "object" && (v)._$litKeyed$ === 1);
}
class TemplateInstance {
           strings;
           startMarker;
           endMarker;
                   parts;
  constructor(compiled) {
    this.strings = compiled.templateEl ? ([]) : ([]);
    const frag = compiled.templateEl.content.cloneNode(true);
    this.startMarker = document.createComment("latter-i-s");
    this.endMarker = document.createComment("latter-i-e");
    const commentMap = new Map();
    const walker = document.createTreeWalker(frag, NodeFilter.SHOW_COMMENT);
    let node = walker.nextNode();
    while (node) {
      const c = node;
      if (c.data.startsWith("latter-p-")) {
        commentMap.set(c.data, c);
      }
      node = walker.nextNode();
    }
    const parts = [];
    for (const d of compiled.descriptors) {
      if (d.kind === "child") {
        const startC = commentMap.get(d.commentText);
        if (startC && startC.parentNode) {
          const endC = document.createComment(`${d.commentText}-end`);
          startC.parentNode.insertBefore(endC, startC.nextSibling);
          parts.push(new ChildPart(startC, endC, d.partIndex));
        }
      } else {
        const el = frag.querySelector(`[${d.markerAttr}]`);
        if (el) {
          if (d.kind === "event") {
            parts.push(new EventPart(el, d.eventName, d.partIndex));
          } else if (d.kind === "prop") {
            parts.push(new PropertyPart(el, d.propName, d.partIndex));
          } else if (d.kind === "bool") {
            parts.push(new BoolAttrPart(el, d.attrName, d.partIndex));
          } else if (d.kind === "attr") {
            parts.push(new AttrPart(el, d.attrName, d.statics, d.partIndices));
          }
        }
      }
    }
    for (const d of compiled.descriptors) {
      if (d.kind !== "child") {
        const el = frag.querySelector(`[${d.markerAttr}]`);
        if (el) el.removeAttribute(d.markerAttr);
      }
    }
    parts.sort((a, b) => a.priority - b.priority);
    this.parts = parts;
    const wrapper = document.createDocumentFragment();
    wrapper.appendChild(this.startMarker);
    wrapper.appendChild(frag);
    wrapper.appendChild(this.endMarker);
    this._fragment = wrapper;
  }
          _fragment;
  mountBefore(parent, refNode) {
    if (this._fragment) {
      parent.insertBefore(this._fragment, refNode);
      this._fragment = null;
    }
  }
  moveBefore(parent, refNode) {
    let cur = this.startMarker;
    while (cur) {
      const next = cur === this.endMarker ? null : cur.nextSibling;
      parent.insertBefore(cur, refNode);
      cur = next;
    }
  }
  remove() {
    let cur = this.startMarker;
    while (cur) {
      const next = cur === this.endMarker ? null : cur.nextSibling;
      if (cur.parentNode) cur.parentNode.removeChild(cur);
      cur = next;
    }
  }
  update(values) {
    for (let i = 0; i < this.parts.length; i += 1) {
      this.parts[i].update(values);
    }
  }
}
function createInstance(res) {
  const compiled = compileTemplate(res.strings);
  const inst = new TemplateInstance(compiled);
  return { strings: res.strings, inst };
}
class ChildPart {
           priority = 0;
          mode = "empty";
          textNode = null;
          singleEntry = null;
          arrayEntries = [];
          keyedMap = new Map();
                   startMarker;
                   endMarker;
                   partIndex;
  constructor(startMarker, endMarker, partIndex) {
    this.startMarker = startMarker;
    this.endMarker = endMarker;
    this.partIndex = partIndex;
  }
          clearBetween() {
    let cur = this.startMarker.nextSibling;
    while (cur && cur !== this.endMarker) {
      const next = cur.nextSibling;
      cur.parentNode?.removeChild(cur);
      cur = next;
    }
    this.textNode = null;
    this.singleEntry = null;
    this.arrayEntries = [];
    this.keyedMap.clear();
    this.mode = "empty";
  }
  update(values) {
    const val = values[this.partIndex];
    const parent = this.endMarker.parentNode;
    if (!parent) return;
    if (val === nothing || val === null || val === undefined || val === false) {
      if (this.mode !== "empty") this.clearBetween();
      return;
    }
    if (isTemplateResult(val)) {
      if (this.mode === "template" && this.singleEntry && this.singleEntry.strings === val.strings) {
        this.singleEntry.inst.update(val.values);
        return;
      }
      this.clearBetween();
      const entry = createInstance(val);
      entry.inst.mountBefore(parent, this.endMarker);
      entry.inst.update(val.values);
      this.singleEntry = entry;
      this.mode = "template";
      return;
    }
    if (isKeyedResult(val)) {
      if (this.mode !== "keyed") {
        this.clearBetween();
        this.mode = "keyed";
      }
      const nextMap = new Map();
      const ordered = [];
      for (let i = 0; i < val.keys.length; i += 1) {
        const k = val.keys[i];
        const tpl = val.templates[i];
        const existing = this.keyedMap.get(k);
        if (existing && existing.strings === tpl.strings) {
          this.keyedMap.delete(k);
          existing.inst.update(tpl.values);
          nextMap.set(k, existing);
          ordered.push(existing);
        } else {
          if (existing) {
            existing.inst.remove();
            this.keyedMap.delete(k);
          }
          const created = createInstance(tpl);
          created.inst.mountBefore(parent, this.endMarker);
          created.inst.update(tpl.values);
          nextMap.set(k, created);
          ordered.push(created);
        }
      }
      for (const leftover of this.keyedMap.values()) {
        leftover.inst.remove();
      }
      // Ensure DOM order matches `ordered` without disturbing focused controls when already ordered.
      let cursor = this.endMarker;
      for (let i = ordered.length - 1; i >= 0; i -= 1) {
        const item = ordered[i].inst;
        if (item.endMarker.nextSibling !== cursor) {
          item.moveBefore(parent, cursor);
        }
        cursor = item.startMarker;
      }
      this.keyedMap = nextMap;
      return;
    }
    if (Array.isArray(val)) {
      const tpls = [];
      let allTemplates = true;
      for (let i = 0; i < val.length; i += 1) {
        const item = val[i];
        if (item === nothing || item === null || item === undefined || item === false) continue;
        if (isTemplateResult(item)) {
          tpls.push(item);
        } else {
          allTemplates = false;
          break;
        }
      }
      if (allTemplates) {
        if (this.mode !== "array") {
          this.clearBetween();
          this.mode = "array";
        }
        while (this.arrayEntries.length > tpls.length) {
          const popped = this.arrayEntries.pop();
          popped?.inst.remove();
        }
        for (let i = 0; i < tpls.length; i += 1) {
          const tpl = tpls[i];
          const existing = this.arrayEntries[i];
          if (existing && existing.strings === tpl.strings) {
            existing.inst.update(tpl.values);
          } else {
            const refNode = existing ? existing.inst.startMarker : this.endMarker;
            if (existing) existing.inst.remove();
            const created = createInstance(tpl);
            created.inst.mountBefore(parent, refNode);
            created.inst.update(tpl.values);
            this.arrayEntries[i] = created;
          }
        }
        return;
      }
      const joined = val
        .filter((x) => x !== nothing && x !== null && x !== undefined && x !== false)
        .map((x) => String(x))
        .join("");
      this.setText(parent, joined);
      return;
    }
    this.setText(parent, String(val));
  }
          setText(parent, str) {
    if (this.mode === "text" && this.textNode) {
      if (this.textNode.data !== str) {
        this.textNode.data = str;
      }
      return;
    }
    this.clearBetween();
    this.textNode = document.createTextNode(str);
    parent.insertBefore(this.textNode, this.endMarker);
    this.mode = "text";
  }
}
class LitElement extends HTMLElement {
  static styles;
           renderRoot;
                   _controllers = new Set();
          _updatePending = false;
          _hasUpdated = false;
          _resolveUpdate = null;
          _updatePromise = Promise.resolve(true);
          _rootEntry = null;
          _stylesAdopted = false;
  constructor() {
    super();
    this.renderRoot = this.attachShadow({ mode: "open" });
  }
  addController(controller) {
    this._controllers.add(controller);
    if (this.isConnected && controller.hostConnected) {
      controller.hostConnected();
    }
  }
  removeController(controller) {
    this._controllers.delete(controller);
  }
  connectedCallback() {
    this._adoptStylesOnce();
    for (const c of this._controllers) {
      c.hostConnected?.();
    }
    this.requestUpdate();
  }
  disconnectedCallback() {
    for (const c of this._controllers) {
      c.hostDisconnected?.();
    }
  }
  get updateComplete() {
    return this._updatePromise;
  }
  requestUpdate() {
    if (this._updatePending) return;
    this._updatePending = true;
    this._updatePromise = new Promise ((resolve) => {
      this._resolveUpdate = resolve;
    });
    queueMicrotask(() => this._performUpdate());
  }
          _adoptStylesOnce() {
    if (this._stylesAdopted) return;
    this._stylesAdopted = true;
    const ctor = this.constructor;
    if (!ctor.styles) return;
    const list = Array.isArray(ctor.styles) ? ctor.styles : [ctor.styles];
    if ("adoptedStyleSheets" in this.renderRoot && typeof CSSStyleSheet !== "undefined") {
      try {
        const sheets = list.map((s) => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(s.styleSheetText);
          return sheet;
        });
        this.renderRoot.adoptedStyleSheets = sheets;
        return;
      } catch {
        // Fallback to <style> element below if constructable stylesheets are unavailable.
      }
    }
    for (const s of list) {
      const styleEl = document.createElement("style");
      styleEl.textContent = s.styleSheetText;
      this.renderRoot.appendChild(styleEl);
    }
  }
          _performUpdate() {
    this._updatePending = false;
    if (!this.isConnected) {
      this._resolveUpdate?.(false);
      this._resolveUpdate = null;
      return;
    }
    this._adoptStylesOnce();
    for (const c of this._controllers) {
      c.hostUpdate?.();
    }
    const rendered = this.render();
    if (isTemplateResult(rendered)) {
      if (this._rootEntry && this._rootEntry.strings === rendered.strings) {
        this._rootEntry.inst.update(rendered.values);
      } else {
        if (this._rootEntry) {
          this._rootEntry.inst.remove();
        }
        const entry = createInstance(rendered);
        entry.inst.mountBefore(this.renderRoot, null);
        entry.inst.update(rendered.values);
        this._rootEntry = entry;
      }
    }
    if (!this._hasUpdated) {
      this._hasUpdated = true;
      this.firstUpdated();
    }
    this.updated();
    for (const c of this._controllers) {
      c.hostUpdated?.();
    }
    this._resolveUpdate?.(true);
    this._resolveUpdate = null;
  }
            render() {
    return nothing;
  }
            firstUpdated() {}
            updated() {}
}

// --- src/constants.ts ---
/**
 * Canonical constants, route maps, issue messages, and Title Case dictionaries for Latter Studio.
 */
const STUDIO_REV = 7;
const MAX_WALLPAPER_UPLOAD_BYTES = 15 * 1024 * 1024;
const DEVICE_VIEW_SLUGS = {
  dashboard: "overview",
  display: "display",
  interface: "interface",
  audio_voice: "audio",
  power: "power",
  presence: "presence",
  tools: "tools",
};
const SYSTEM_VIEW_SLUGS = {system_overview: "overview", shared_entities: "shared", remotes: "remotes", system_sync: "groups", area_tracking: "presence", system_tools: "tools"};
const VIEW_TITLES = {
  system_overview: "Overview",
  shared_entities: "Shared Entities",
  remotes: "Media & Remotes",
  system_sync: "Device Groups",
  area_tracking: "BLE & Area Presence",
  system_tools: "Tools",
  select_device_prompt: "All Devices",
  dashboard: "Overview",
  display: "Display",
  interface: "Interface",
  audio_voice: "Audio",
  power: "Power",
  presence: "Presence",
  tools: "Tools",
};
const _typecheckViewMaps
  = [DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS, VIEW_TITLES];
void _typecheckViewMaps;
// Messages for Latter's Home Assistant Repairs (kind = translation key in strings.json).
const ISSUE_TEXT = {
  link_ma_player: () => "Not linked to its Music Assistant player.",
  missing_mapped_entity: (i) =>
    `A chosen entity no longer exists${i.detail ? `: ${i.detail}` : ""}.`,
  ble_no_proxies: () =>
    "BLE Area tracking is on, but no Bluetooth proxy is assigned to an Area.",
  slot_push_failing: () =>
    "Latter can't send Area and browse pages to this Device.",
  device_crashed: (i) =>
    i.detail === "stall"
      ? "Restarted itself after its main loop stalled for 30 seconds."
      : `Restarted after a crash${i.detail ? ` (${i.detail})` : ""}.`,
  device_brownout: () => "Restarted after a power dip (brownout).",
  firmware_rolled_back: () =>
    "A firmware update failed to start; the previous firmware is running.",
};
// Canonical 7 Dock App tokens (`protocol.py` DOCK_APP_TOKENS).
const DOCK_APPS_CATALOG = [
  {token: "music", label: "Music"},
  {token: "alarm", label: "Home Hub"},
  {token: "area", label: "Area"},
  {token: "remote", label: "Remote"},
  {token: "camera", label: "Cameras"},
  {token: "games", label: "Games"},
  {token: "tools", label: "Tools"},
];
// Canonical 8 Area Category tokens (`protocol.py` AREA_CATEGORY_TOKENS).
const AREA_CATEGORIES_CATALOG = [
  { token: "scene", label: "Scenes" },
  { token: "light", label: "Lights" },
  { token: "cover", label: "Blinds & Curtains" },
  { token: "fan", label: "Fans" },
  { token: "switch", label: "Switches" },
  { token: "climate", label: "Climate" },
  { token: "media", label: "Media" },
  { token: "all", label: "All Devices" },
];
const DEFAULT_AREA_CATEGORIES_TOKENS = [
  "scene",
  "light",
  "cover",
  "fan",
  "switch",
  "climate",
  "media",
];
// Canonical 5 Activity Card source keys (`protocol.py` ACTIVITY_SOURCE_KEYS).
const ACTIVITY_SOURCES_CATALOG = [
  { id: "calendar", label: "Calendar" },
  { id: "music_queue", label: "Music Queue" },
  { id: "stopwatch", label: "Stopwatch" },
  { id: "alarms", label: "Alarms" },
  { id: "timers", label: "Timers" },
];
const SECURITY_PIN_POLICY_OPTIONS = [
  { value: "auto", label: "Auto (Recommended)" },
  { value: "allow", label: "Allow Without PIN" },
  { value: "require_pin", label: "Require PIN" },
  { value: "block", label: "Block Unlock & Disarm" },
];
const WALLPAPER_ROTATION_OPTIONS = [
  { value: 0, label: "Do not rotate" },
  { value: 5, label: "Every 5 minutes" },
  { value: 15, label: "Every 15 minutes" },
  { value: 30, label: "Every 30 minutes" },
  { value: 60, label: "Every hour" },
  { value: 360, label: "Every 6 hours" },
  { value: 1440, label: "Once a day" },
];
const DEFAULT_DEVICE_GROUP_IDS = new Set([
  "unassigned",
  "handhelds",
  "wearables",
  "bedrooms",
  "common_areas",
  "wall_panels",
]);
const LABEL_MINOR_WORDS = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "of",
  "to",
  "in",
  "on",
  "for",
  "with",
]);
const LABEL_ACRONYMS = {
  ble: "BLE",
  cpu: "CPU",
  db: "dB",
  dbm: "dBm",
  dns: "DNS",
  esp: "ESP",
  esphome: "ESPHome",
  ha: "HA",
  http: "HTTP",
  id: "ID",
  imu: "IMU",
  ip: "IP",
  ips: "IPS",
  led: "LED",
  ma: "MA",
  mac: "MAC",
  mic: "Mic",
  ota: "OTA",
  pin: "PIN",
  pmu: "PMU",
  psram: "PSRAM",
  ram: "RAM",
  rgb: "RGB",
  rssi: "RSSI",
  sdk: "SDK",
  sram: "SRAM",
  ssid: "SSID",
  tts: "TTS",
  ui: "UI",
  url: "URL",
  usb: "USB",
  uuid: "UUID",
  va: "VA",
  wifi: "Wi-Fi",
  "wi-fi": "Wi-Fi",
};

// --- src/utils/format.ts ---
/**
 * Locale-aware formatters, Title Case entity label converter (D-013), and color helpers.
 * Note: Avoid literal `#RRGGBB` color constants here so `[STUDIO TOKENS]` stays 100% pure.
 */
function hassLanguage(hass) {
  return String(hass?.locale?.language || hass?.language || navigator.language || "en");
}
function fmtNumber(
  value,
  hass,
  maximumFractionDigits = 1,
) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), { maximumFractionDigits }).format(num);
  } catch {
    return String(num);
  }
}
function fmtPercent(
  value,
  hass,
) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "percent",
      maximumFractionDigits: 0,
    }).format(num / 100);
  } catch {
    return `${Math.round(num)}%`;
  }
}
function fmtDistance(
  meters,
  hass,
  feet,
) {
  const isImperial = hass?.config?.unit_system?.length === "mi";
  if (isImperial) {
    const hasFeet = feet !== null && feet !== undefined && Number.isFinite(Number(feet));
    const hasMeters = meters !== null && meters !== undefined && Number.isFinite(Number(meters));
    if (!hasFeet && !hasMeters) return "—";
    const ft = hasFeet ? Number(feet) : Number(meters) * 3.28084;
    try {
      return new Intl.NumberFormat(hassLanguage(hass), {
        style: "unit",
        unit: "foot",
        maximumFractionDigits: 1,
      }).format(ft);
    } catch {
      return `${ft.toFixed(1)} ft`;
    }
  }
  if (meters === null || meters === undefined || !Number.isFinite(Number(meters))) return "—";
  const m = Number(meters);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "unit",
      unit: "meter",
      maximumFractionDigits: 1,
    }).format(m);
  } catch {
    return `${m.toFixed(1)} m`;
  }
}
function fmtAgo(
  secondsAgo,
  hass,
) {
  if (secondsAgo === null || secondsAgo === undefined || !Number.isFinite(Number(secondsAgo))) {
    return "—";
  }
  const secs = Math.max(0, Math.round(Number(secondsAgo)));
  try {
    const rtf = new Intl.RelativeTimeFormat(hassLanguage(hass), { numeric: "auto" });
    if (secs < 60) return rtf.format(-secs, "second");
    if (secs < 3600) return rtf.format(-Math.round(secs / 60), "minute");
    if (secs < 86400) return rtf.format(-Math.round(secs / 3600), "hour");
    return rtf.format(-Math.round(secs / 86400), "day");
  } catch {
    return `${secs}s ago`;
  }
}
function fmtDateTime(
  ts,
  hass,
) {
  if (ts === null || ts === undefined || ts === "") return "";
  const date = typeof ts === "number" ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  const useServerTz = hass?.locale?.time_zone === "server" && Boolean(hass?.config?.time_zone);
  const opts = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  };
  if (useServerTz && hass?.config?.time_zone) {
    opts.timeZone = hass.config.time_zone;
  }
  try {
    return new Intl.DateTimeFormat(hassLanguage(hass), opts).format(date);
  } catch {
    return date.toISOString();
  }
}
function capitalizeSegment(seg) {
  if (!seg) return seg;
  const low = seg.toLowerCase();
  if (LABEL_ACRONYMS[low]) return LABEL_ACRONYMS[low];
  if (/^[a-z]+[A-Z]/.test(seg) || /^[A-Z0-9]{2,}$/.test(seg)) return seg;
  return seg.charAt(0).toUpperCase() + seg.slice(1);
}
function entityLabel(rawName) {
  const cleaned = String(rawName || "").trim();
  if (!cleaned) return "—";
  const words = cleaned.split(/\s+/).filter(Boolean);
  return words
    .map((word, idx) => {
      const m = /^([([{"']*)(.*?)([)\]}"':,.?]*)$/.exec(word);
      const lead = m ? m[1] : "";
      const core = m ? m[2] : word;
      const trail = m ? m[3] : "";
      if (!core) return word;
      // Preserve parenthesized units such as (ms), (s), (dB), (dBm), (%).
      if (lead === "(" && trail === ")" && /^(ms|s|m|h|dB|dBm|Hz|kHz|MHz|V|mV|A|mA|W|%|°C|°F)$/.test(core)) {
        return word;
      }
      const isEdge = idx === 0 || idx === words.length - 1;
      const low = core.toLowerCase();
      if (!isEdge && LABEL_MINOR_WORDS.has(low)) {
        return `${lead}${low}${trail}`;
      }
      if (LABEL_ACRONYMS[low]) {
        return `${lead}${LABEL_ACRONYMS[low]}${trail}`;
      }
      const hyph = core
        .split("-")
        .map((seg) => capitalizeSegment(seg))
        .join("-");
      return `${lead}${hyph}${trail}`;
    })
    .join(" ");
}
function issueMessage(issue) {
  const kind = String(issue.kind || issue.key || "");
  const fn = ISSUE_TEXT[kind];
  if (fn) return fn(issue);
  const label = kind ? kind.replace(/_/g, " ") : "issue";
  return `Repair: ${label}.`;
}
function isGroupCustomized(status) {
  if (!status) return false;
  if (typeof status === "string") return status === "customized";
  if (typeof status === "object" && "in_sync" in status) {
    return (status).in_sync === false;
  }
  return false;
}
function rssiToPercent(rssi) {
  if (rssi === null || rssi === undefined || !Number.isFinite(Number(rssi))) return 0;
  const clamped = Math.max(-95, Math.min(-35, Number(rssi)));
  return Math.round(((clamped + 95) / 60) * 100);
}
function isValidHexColor(val) {
  const s = String(val || "").trim();
  if (s.length !== 7 || s.charCodeAt(0) !== 35) return false;
  for (let i = 1; i < 7; i += 1) {
    const code = s.charCodeAt(i);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 70;
    const isLower = code >= 97 && code <= 102;
    if (!isDigit && !isUpper && !isLower) return false;
  }
  return true;
}
function byteToHex(b) {
  const clamped = Math.max(0, Math.min(255, Math.round(b)));
  return clamped.toString(16).padStart(2, "0").toUpperCase();
}
function rgbBytesToHex(r, g, b) {
  return String.fromCharCode(35) + byteToHex(r) + byteToHex(g) + byteToHex(b);
}
function hsvToRgbJS(h, s, v) {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (h < 60) [r1, g1, b1] = [c, x, 0];
  else if (h < 120) [r1, g1, b1] = [x, c, 0];
  else if (h < 180) [r1, g1, b1] = [0, c, x];
  else if (h < 240) [r1, g1, b1] = [0, x, c];
  else if (h < 300) [r1, g1, b1] = [x, 0, c];
  else [r1, g1, b1] = [c, 0, x];
  return [
    Math.round((r1 + m) * 255),
    Math.round((g1 + m) * 255),
    Math.round((b1 + m) * 255),
  ];
}
function hsvToHex(h, s, v) {
  const [r, g, b] = hsvToRgbJS(h, s, v);
  return rgbBytesToHex(r, g, b);
}
function defaultThemeHex(hostEl) {
  if (hostEl && typeof getComputedStyle === "function") {
    const raw = getComputedStyle(hostEl).getPropertyValue("--primary-color").trim();
    if (isValidHexColor(raw)) return raw.toUpperCase();
  }
  return rgbBytesToHex(0, 154, 199);
}
async function copyTextToClipboard(text) {
  if (!text) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall back to offscreen textarea selection below.
  }
  try {
    const ta = document.createElement("textarea");
    ta.className = "offscreen";
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
function triggerJsonDownload(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function navigateHaPath(path, replace = false) {
  if (!path) return;
  if (replace) {
    globalThis.history.replaceState(null, "", path);
  } else {
    globalThis.history.pushState(null, "", path);
  }
  globalThis.dispatchEvent(new Event("location-changed", { bubbles: true, composed: true }));
}

// --- src/components/controls.ts ---
/**
 * Shared Lit UI controls, declarative card/row/slot helpers, native ESPHome entity rows, and table headers.
 * Note: Event bindings (`@click`, `@change`) always precede `class="..."` / `role="radio"` attributes.
 */
function renderCard(opts) {
  const headingEl = opts.heading ?? html`<h3 class="card-title">${opts.title || ""}</h3>`;
  const headerInner =
    opts.subtitle || opts.headerActions
      ? html`<div class="card-heading">
            ${headingEl}
            ${opts.subtitle ? html`<p class="card-subtitle">${opts.subtitle}</p>` : nothing}
          </div>
          ${opts.headerActions && opts.headerActions !== nothing
            ? html`<div class="card-header-actions">${opts.headerActions}</div>`
            : nothing}`
      : headingEl;
  const contentCls = opts.contentClass ? `card-content ${opts.contentClass}` : "card-content";
  return html`<div id=${opts.id || nothing} class="card${opts.danger ? " danger" : ""}">
    <div class="card-header">${headerInner}</div>
    <div class=${contentCls}>${opts.body}</div>
    ${opts.footerActions && opts.footerActions !== nothing
      ? html`<div class="card-actions">${opts.footerActions}</div>`
      : nothing}
  </div>`;
}
function renderSettingsRow(opts) {
  const labelEl =
    opts.labelHtml ??
    (opts.forId
      ? html`<label for=${opts.forId} class="row-label">${opts.label || ""}</label>`
      : html`<span class="row-label">${opts.label || ""}</span>`);
  return html`<div id=${opts.id || nothing} class="settings-row${opts.stacked ? " stacked" : ""}">
    <div class="settings-row-text">
      ${labelEl}
      ${opts.description
        ? html`<p id=${opts.descId || nothing} class="row-description">${opts.description}</p>`
        : nothing}
    </div>
    <div class="settings-row-control">${opts.control}</div>
  </div>`;
}
function renderSelectRow(opts) {
  const cur = String(opts.value ?? "");
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: opts.descId,
    control: html`<select
      id=${opts.id || nothing}
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .value=${cur}
      @change=${(ev) => opts.onChange((ev.currentTarget).value)}
    >
      ${opts.rawOptions
        ? opts.rawOptions.map(
            (o) => html`<option value=${o.value} ?selected=${o.value === cur}>${o.label}</option>`,
          )
        : renderSelectOptions(opts.choices, cur, opts.emptyOptionLabel)}
    </select>`,
  });
}
function renderSwitchRow(opts) {
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    control: html`<input
      type="checkbox"
      id=${opts.id || nothing}
      role="switch"
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .checked=${opts.checked}
      @change=${(ev) => opts.onChange((ev.currentTarget).checked)}
      class="switch"
    />`,
  });
}
function renderEntitySlotList(opts) {
  return html`<div id=${opts.id} class="stack">
    ${opts.items.length
      ? opts.items.map(
          (val, idx) => html`<div class="list-row">
            <div class="stacked-field list-row-grow">
              ${opts.slotLabel
                ? html`<span class="field-label">${opts.slotLabel(idx)}</span>`
                : nothing}
              <select
                aria-label=${opts.selectAriaLabel}
                .value=${val}
                @change=${(ev) =>
                  opts.onChange(idx, (ev.currentTarget).value)}
              >
                ${renderSelectOptions(opts.choices, val, opts.emptyOptionLabel)}
              </select>
            </div>
            ${opts.extraActions ? opts.extraActions(val, idx) : nothing}
            ${renderTrashIconButton(opts.removeAriaLabel, () => opts.onRemove(idx))}
          </div>`,
        )
      : html`<p class="empty-state">${opts.emptyStateText}</p>`}
  </div>`;
}
function renderSelectOptions(
  choices,
  selectedId,
  emptyOptionLabel = "None",
) {
  const cur = String(selectedId || "");
  const list = choices || [];
  const hasSelected = !cur || list.some((c) => c.id === cur);
  const out = [
    html`<option value="" ?selected=${cur === ""}>${emptyOptionLabel}</option>`,
  ];
  if (cur && !hasSelected) {
    out.push(html`<option value=${cur} selected>${cur} (missing)</option>`);
  }
  for (const item of list) {
    out.push(
      html`<option value=${item.id} ?selected=${item.id === cur}>${item.name || item.id}</option>`,
    );
  }
  return out;
}
function renderTrashIconButton(ariaLabel, onRemove) {
  return html`<button
    type="button"
    aria-label=${ariaLabel}
    @click=${onRemove}
    class="btn-icon danger"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9m0 5h2v9H9V8m4 0h2v9h-2V8Z" />
    </svg>
  </button>`;
}
function renderSortHeader(
  store,
  field,
  label,
) {
  const isActive = store.deviceSortField === field;
  const ariaSort = isActive ? (store.deviceSortAsc ? "ascending" : "descending") : "none";
  const onSort = () => {
    if (store.deviceSortField === field) {
      store.deviceSortAsc = !store.deviceSortAsc;
    } else {
      store.deviceSortField = field;
      store.deviceSortAsc = true;
    }
    store.host.requestUpdate();
  };
  return html`<th aria-sort=${ariaSort}>
    <button type="button" @click=${onSort} class="sort-btn">${label}</button>
  </th>`;
}
function renderNativeControlRow(store, item) {
  const label = entityLabel(item.name || item.entity_id);
  const dom = item.domain;
  const st = String(item.state ?? "");
  const prefKey = item.pref_key || "";
  const unavailable = !prefKey && (st === "unavailable" || st === "unknown");
  if (dom === "switch") {
    const isOn = st === "on";
    const onToggle = (ev) => {
      const checked = (ev.currentTarget).checked;
      if (prefKey) {
        store.stageDeviceSetting(prefKey, checked);
      } else {
        void store.espAction(item.entity_id, checked ? "turn_on" : "turn_off", checked ? "on" : "off");
      }
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        ?disabled=${unavailable}
        .checked=${isOn}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }
  if (dom === "select") {
    const opts = item.options || [];
    const onChange = (ev) => {
      const nextVal = (ev.currentTarget).value;
      if (prefKey) {
        store.stageDeviceSetting(prefKey, nextVal);
      } else {
        void store.espSelect(item.entity_id, nextVal);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${st} @change=${onChange}>
        ${opts.map((opt) => html`<option value=${opt} ?selected=${opt === st}>${opt}</option>`)}
      </select>`,
    });
  }
  if (dom === "number") {
    const min = item.min ?? 0;
    const max = item.max ?? 100;
    const step = item.step ?? 1;
    const numVal = Number.isFinite(Number(st)) ? Number(st) : min;
    const unitSuffix = item.unit ? ` ${item.unit}` : "";
    const onCommit = (ev) => {
      const raw = Number((ev.currentTarget).value);
      if (Number.isFinite(raw)) {
        if (prefKey) {
          store.stageDeviceSetting(prefKey, raw);
        } else {
          void store.espNumber(item.entity_id, raw);
        }
      }
    };
    if (max - min <= 250 && item.mode !== "box") {
      return renderSettingsRow({
        label,
        control: html`<span class="kv-value">${fmtNumber(numVal, store.hass)}${unitSuffix}</span>
          <input
            type="range"
            aria-label=${label}
            min=${String(min)}
            max=${String(max)}
            step=${String(step)}
            ?disabled=${unavailable}
            .value=${String(numVal)}
            @change=${onCommit}
          />`,
      });
    }
    return renderSettingsRow({
      label,
      control: html`<input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          ?disabled=${unavailable}
          .value=${String(numVal)}
          @change=${onCommit}
        />
        ${item.unit ? html`<span class="help-text">${item.unit}</span>` : nothing}`,
    });
  }
  if (dom === "button") {
    const buttonUnavailable = st === "unavailable";
    const toastMsg = label.toLowerCase().includes("restart")
      ? "Restarting Device…"
      : `Triggered "${label}"`;
    const onRun = () => {
      if (item.device_command) {
        void store.runDeviceAction(item.device_command, toastMsg);
      } else {
        void store.espAction(item.entity_id, "press", undefined, toastMsg);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<button
        type="button"
        ?disabled=${buttonUnavailable}
        @click=${onRun}
        class="btn btn-secondary btn-compact"
      >
        Run
      </button>`,
    });
  }
  if (dom === "update") {
    const hasUpdate = st === "on";
    return renderSettingsRow({
      label,
      control: html`<span class="chip ${hasUpdate ? "chip-warning" : ""}">${hasUpdate ? "Update available" : "Up to date"}</span>
        ${hasUpdate
          ? html`<button
              type="button"
              @click=${() => void store.espAction(item.entity_id, "install")}
              class="btn btn-primary btn-compact"
            >
              Install
            </button>`
          : nothing}`,
    });
  }
  const displayVal = unavailable
    ? "—"
    : item.unit && Number.isFinite(Number(st))
      ? `${fmtNumber(Number(st), store.hass)} ${item.unit}`
      : st || "—";
  return html`<div class="kv-row">
    <span>${label}</span>
    <strong>${displayVal}</strong>
  </div>`;
}
const QUICK_ACTION_RANK = {
  find_my: 0,
  voice: 1,
  screensaver: 2,
  hibernate: 3,
  restart: 4,
  other: 5,
};
function quickActionKind(item) {
  const nameLow = (item.name || "").toLowerCase();
  const idTail = item.entity_id.includes(".")
    ? item.entity_id.split(".", 2)[1].toLowerCase()
    : item.entity_id.toLowerCase();
  if (
    item.device_class === "identify" ||
    nameLow.includes("find my") ||
    idTail.endsWith("find_my_device") ||
    idTail.includes("_find_my")
  ) {
    return "find_my";
  }
  if (
    item.device_class === "restart" ||
    nameLow.includes("restart") ||
    idTail.endsWith("_restart_device") ||
    idTail.endsWith("_restart")
  ) {
    return "restart";
  }
  if (nameLow.includes("screensaver") || idTail.includes("screensaver")) {
    return "screensaver";
  }
  if (nameLow.includes("hibernate") || idTail.includes("hibernate")) {
    return "hibernate";
  }
  if (
    nameLow.includes("voice") ||
    nameLow.includes("assist") ||
    idTail.includes("trigger_voice") ||
    idTail.includes("trigger_va")
  ) {
    return "voice";
  }
  return "other";
}
function renderQuickActionIcon(kind) {
  if (kind === "find_my") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8m0-14a6 6 0 1 0 6 6 6 6 0 0 0-6-6m0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4m0-6a2 2 0 1 0 2 2 2 2 0 0 0-2-2Z"
      />
    </svg>`;
  }
  if (kind === "voice") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3m7 9c0 3.53-2.61 6.44-6 6.93V21h-2v-3.07c-3.39-.49-6-3.4-6-6.93h2a5 5 0 0 0 10 0h2Z"
      />
    </svg>`;
  }
  if (kind === "screensaver") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20 3H4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h6v2H7v2h10v-2h-3v-2h6a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2m0 13H4V5h16v11M11.2 6.8a3.8 3.8 0 1 0 2.4 6 3.5 3.5 0 0 1-2.4-6m5.3-.6.65 1.65 1.65.65-1.65.65-.65 1.65-.65-1.65-1.65-.65 1.65-.65.65-1.65Z"
      />
    </svg>`;
  }
  if (kind === "hibernate") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12a6 6 0 0 1-6 6 6 6 0 0 1-6-6c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.961 7.961 0 0 0 4 12a8 8 0 0 0 8 8 8 8 0 0 0 8-8c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2V3Z"
      />
    </svg>`;
  }
  if (kind === "restart") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h10l-3.5 7H17l-7 13v-8H6l1-12Z" />
  </svg>`;
}
function sortQuickActionButtons(
  items,
) {
  return [...items].sort((a, b) => {
    const ra = QUICK_ACTION_RANK[quickActionKind(a)];
    const rb = QUICK_ACTION_RANK[quickActionKind(b)];
    if (ra !== rb) return ra - rb;
    return `${a.name || ""} ${a.entity_id}`
      .toLowerCase()
      .localeCompare(`${b.name || ""} ${b.entity_id}`.toLowerCase());
  });
}
function renderQuickActionGrid(
  store,
  buttons,
) {
  if (!buttons.length) return nothing;
  const ordered = sortQuickActionButtons(buttons);
  return html`<div class="quick-action-grid" role="group" aria-label="Device Quick Actions">
    ${ordered.map((item) => {
      const kind = quickActionKind(item);
      const label = entityLabel(item.name || item.entity_id);
      const buttonUnavailable = String(item.state ?? "") === "unavailable";
      const toastMsg =
        kind === "restart"
          ? "Restarting Device…"
          : kind === "hibernate"
            ? "Hibernating Device…"
            : `Triggered "${label}"`;
      const onTrigger = () => {
        if (item.device_command) {
          void store.runDeviceAction(item.device_command, toastMsg);
        } else {
          void store.espAction(item.entity_id, "press", undefined, toastMsg);
        }
      };
      return html`<button
        type="button"
        data-entity-id=${item.entity_id}
        ?disabled=${buttonUnavailable}
        @click=${onTrigger}
        class="btn btn-secondary quick-action-btn"
      >
        ${renderQuickActionIcon(kind)}
        <span>${label}</span>
      </button>`;
    })}
  </div>`;
}

// --- src/components/dialogs.ts ---
/**
 * Native `<dialog>` Modals for Latter Studio (Remove Device, Reset Device, Add BLE Tag, Custom Color Wheel).
 * Uses component-scoped pointer capture on `<canvas>` — zero `window.*` listeners.
 */
let cwWheelPainted = false;
function paintHsvColorWheel(canvas) {
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
function pickWheelHexFromEvent(canvas, ev) {
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
function syncStudioDialogs(renderRoot, store) {
  const pairs = [
    ["latter-rm-modal", store.removeModal.open],
    ["latter-reset-modal", store.resetModal.open],
    ["latter-add-dev-modal", store.addBleModal.open],
    ["latter-cw-modal", store.colorWheelModal.open],
  ];
  for (const [id, wantOpen] of pairs) {
    const dlg = renderRoot.getElementById(id);
    if (!dlg) continue;
    if (wantOpen && !dlg.open) {
      try {
        dlg.showModal();
      } catch {
        dlg.setAttribute("open", "");
      }
    } else if (!wantOpen && dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
  }
  if (store.colorWheelModal.open && !cwWheelPainted) {
    const canvas = renderRoot.getElementById("latter-cw-canvas");
    if (canvas) {
      paintHsvColorWheel(canvas);
      cwWheelPainted = true;
    }
  } else if (!store.colorWheelModal.open) {
    cwWheelPainted = false;
  }
}
function renderStudioDialogs(store) {
  const persons = store.state?.catalog?.persons || [];
  const candidates = store.state?.discovered_ble_devices || [];
  const onBackdropClick = (ev, closeFn) => {
    if (ev.target === ev.currentTarget) {
      closeFn();
    }
  };
  const onCwPointerDown = (ev) => {
    const pev = ev;
    const canvas = pev.currentTarget;
    canvas.setPointerCapture?.(pev.pointerId);
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };
  const onCwPointerMove = (ev) => {
    const pev = ev;
    if (pev.buttons === 0) return;
    const canvas = pev.currentTarget;
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };
  const onCwPointerUp = (ev) => {
    const pev = ev;
    const canvas = pev.currentTarget;
    if (canvas.hasPointerCapture?.(pev.pointerId)) {
      canvas.releasePointerCapture(pev.pointerId);
    }
  };
  const onCwHexInput = (ev) => {
    const raw = (ev.currentTarget).value;
    store.colorWheelModal = { ...store.colorWheelModal, hex: raw.toUpperCase() };
    store.host.requestUpdate();
  };
  const onCwNameInput = (ev) => {
    store.colorWheelModal = {
      ...store.colorWheelModal,
      name: (ev.currentTarget).value,
    };
  };
  const cwValidHex = isValidHexColor(store.colorWheelModal.hex)
    ? store.colorWheelModal.hex
    : "";
  return html`
    <dialog
      id="latter-rm-modal"
      aria-labelledby="latter-rm-title"
      @cancel=${() => store.closeRemoveDeviceModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeRemoveDeviceModal())}
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
      @click=${(ev) => onBackdropClick(ev, () => store.closeResetDeviceModal())}
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
      @click=${(ev) => onBackdropClick(ev, () => store.closeAddBleModal())}
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
            @change=${(ev) =>
              store.selectBleCandidateInModal((ev.currentTarget).value)}
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
            @input=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                name: (ev.currentTarget).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <span class="field-label">Target Address or Entity</span>
          <input
            type="text"
            id="ble-custom-addr"
            placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
            .value=${store.addBleModal.address}
            @input=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                address: (ev.currentTarget).value,
              };
            }}
            class="mono"
          />
        </div>
        <div class="stacked-field">
          <label for="ble-custom-person">Assigned Person (Optional)</label>
          <select
            id="ble-custom-person"
            .value=${store.addBleModal.assignedPerson}
            @change=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                assignedPerson: (ev.currentTarget).value,
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
      @click=${(ev) => onBackdropClick(ev, () => store.closeColorWheelModal())}
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
  `;
}

// --- src/api/ws-client.ts ---
/**
 * Admin-gated WebSocket & Bearer-authenticated XHR multipart client for Latter Studio.
 * Enforces `studio_rev` on every read/mutation call and surfaces `studio_rev_mismatch`.
 */
const SYSTEM_WS_COMMANDS = new Set([
  "set_ble_area_offset",
  "set_area_fusion",
  "auto_calibrate_here",
  "system_entity_action",
  "send_announcement",
  "check_system_updates",
  "clear_internal_logs",
  "remove_device",
  "add_ble_device",
  "create_device_group",
  "delete_device_group",
  "sync_device_group",
  "seed_group_baseline",
  "set_group_device_setting",
  "test_doorbell_speaker",
  "delete_system_wallpaper",
  "save_system_config",
  "rotate_signing_key",
  "set_security_pin",
]);
const DEVICE_WS_COMMANDS = new Set([
  "esphome_entity_action",
  "device_action",
  "select_wallpaper",
  "toggle_wallpaper_favorite",
  "delete_wallpaper",
  "save_device_config",
]);
function isStudioRevMismatchError(err) {
  if (!err || typeof err !== "object") return false;
  const code = String((err).code || "");
  return code === "studio_rev_mismatch";
}
function formatWsError(err, fallback = "Action failed") {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err === "object" && "message" in err && (err).message) {
    return String((err).message);
  }
  return fallback;
}
class StudioWsClient {
          hassRef = null;
                   onRevMismatch;
  constructor(onRevMismatch) {
    this.onRevMismatch = onRevMismatch;
  }
  setHass(hass) {
    this.hassRef = hass;
  }
  get hass() {
    return this.hassRef;
  }
          requireHass() {
    if (!this.hassRef) {
      throw new Error("Home Assistant connection is not ready");
    }
    return this.hassRef;
  }
          async callWS (msg) {
    const hass = this.requireHass();
    try {
      return await hass.callWS (msg);
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }
  async getState(options
   ) {
    const res = await this.callWS ({
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
    options
     ,
    onEvent,
  ) {
    const hass = this.requireHass();
    if (!hass.connection) {
      throw new Error("Home Assistant WebSocket connection is unavailable");
    }
    try {
      const msg = {
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
    cmd,
    payload = {},
    selectedSubentryId,
  ) {
    if (!SYSTEM_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown System command: ${cmd}`);
    }
    return this.callWS ({
      type: "latter/system/command",
      command: cmd,
      subentry_id: selectedSubentryId || null,
      payload,
      studio_rev: STUDIO_REV,
    });
  }
  async runDeviceCommand(
    subentryId,
    cmd,
    payload = {},
  ) {
    if (!DEVICE_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown Device command: ${cmd}`);
    }
    if (!subentryId) {
      throw new Error("Choose a Device first");
    }
    return this.callWS ({
      type: "latter/device/command",
      command: cmd,
      subentry_id: subentryId,
      payload,
      studio_rev: STUDIO_REV,
    });
  }
  async exportBackup(scope, subentryId) {
    if (scope === "device") {
      if (!subentryId) throw new Error("Choose a Device to export");
      return this.callWS ({
        type: "latter/device/export",
        subentry_id: subentryId,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS ({
      type: "latter/system/export",
      studio_rev: STUDIO_REV,
    });
  }
  async importBackup(options
   ) {
    if (options.scope === "device") {
      if (!options.targetSubentryId) {
        throw new Error("Choose the Device to restore this backup onto");
      }
      return this.callWS ({
        type: "latter/device/import",
        subentry_id: options.targetSubentryId,
        bundle: options.bundle,
        restore_esphome_entities: options.restoreEspHomeEntities,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS ({
      type: "latter/system/import",
      subentry_id: options.selectedSubentryId || null,
      bundle: options.bundle,
      restore_esphome_entities: options.restoreEspHomeEntities,
      studio_rev: STUDIO_REV,
    });
  }
  async resetDevice(options
   ) {
    return this.callWS ({
      type: "latter/device/reset",
      subentry_id: options.subentryId,
      device_settings: options.deviceSettings,
      latter_options: options.latterOptions,
      studio_rev: STUDIO_REV,
    });
  }
  async signHaPath(path, expires = 300) {
    const signed = await this.callWS ({
      type: "auth/sign_path",
      path,
      expires,
    });
    if (!signed || !signed.path) {
      throw new Error("Could not sign Home Assistant path");
    }
    return signed.path;
  }
          async getAccessToken(forceRefresh = false) {
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
  async uploadWallpaperMultipart(options
   ) {
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
    const sendOnce = (bearerToken) =>
      new Promise ((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", UPLOAD_PATH, true);
        xhr.setRequestHeader("Authorization", `Bearer ${bearerToken}`);
        xhr.responseType = "json";
        if (xhr.upload && options.onProgress) {
          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable && ev.total > 0) {
              options.onProgress?.(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
            }
          };
        }
        xhr.onload = () => {
          const body =
            xhr.response && typeof xhr.response === "object"
              ? (xhr.response)
              : null;
          resolve({ status: xhr.status, body });
        };
        xhr.onerror = () => {
          reject(new Error("Network error while uploading wallpaper"));
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
        wallpapers: Array.isArray(body?.wallpapers) ? (body.wallpapers) : undefined,
        system_wallpapers: Array.isArray(body?.system_wallpapers)
          ? (body.system_wallpapers)
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

// --- src/state/dialogs-tools-ops.ts ---
/**
 * Security PIN, signing key rotation, diagnostics, modal dialogs (Remove/Reset/Add BLE/Color Wheel),
 * firmware update checks, announcements, backup/restore, and System & Device Logs operations.
 */
async function saveSecurityPinOp(store, fromScope) {
  const rawPin = (fromScope === "device" ? store.devicePinDraft : store.systemPinDraft).trim();
  if (!/^\d{4,12}$/.test(rawPin)) {
    store.showToast("Security PIN must be 4 to 12 digits", true);
    return;
  }
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload = { pin: rawPin };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Saved Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not save Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}
async function clearSecurityPinOp(store, fromScope) {
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload = { clear: true };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}
async function rotateSigningKeyOp(store) {
  try {
    const res = await store.ws.runSystemCommand(
      "rotate_signing_key",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Rotated HTTP resource signing key");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not rotate signing key"), true);
  }
}
async function downloadDeviceDiagnosticsOp(store) {
  const entryId = store.state?.links?.entry_id || "";
  const latterDeviceId = store.state?.links?.latter_device_id || "";
  if (!entryId) {
    store.showToast("Diagnostics entry ID is not available", true);
    return;
  }
  const rawPath = latterDeviceId
    ? `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}/device/${encodeURIComponent(latterDeviceId)}`
    : `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
  try {
    const signedPath = await store.ws.signHaPath(rawPath, 300);
    const a = document.createElement("a");
    a.href = signedPath;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not download diagnostics"), true);
  }
}
function openColorWheelModalOp(store, targetScope) {
  const initial =
    targetScope === "device" && isValidHexColor(store.state?.config?.device_custom_color)
      ? String(store.state?.config?.device_custom_color).toUpperCase()
      : defaultThemeHex(store.host);
  store.colorWheelModal = {
    open: true,
    targetScope,
    hex: initial,
    name: "",
    busy: false,
  };
  store.host.requestUpdate();
}
async function saveColorWheelSelectionOp(store) {
  const hex = store.colorWheelModal.hex.trim().toUpperCase();
  if (!isValidHexColor(hex)) {
    store.showToast("Enter a valid 6-digit hex color", true);
    return;
  }
  const name = store.colorWheelModal.name.trim() || hex;
  const existing = [...(store.state?.system_config?.custom_palettes || [])];
  if (!existing.some((p) => p.hex.toUpperCase() === hex)) {
    existing.push({ name, hex });
    store.stageSystemSetting("custom_palettes", existing);
    await store.flushSystemSettings();
  }
  if (store.colorWheelModal.targetScope === "device" && store.activeSubentryId) {
    store.applyDeviceCustomColor(hex, true);
    await store.flushDeviceBucket(store.activeSubentryId);
  }
  store.closeColorWheelModal();
}
async function confirmRemoveDeviceOp(store) {
  const subId = store.removeModal.subentryId;
  if (!subId) return;
  store.removeModal = { ...store.removeModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "remove_device",
      { subentry_id: subId },
      store.activeSubentryId || null,
    );
    store.closeRemoveDeviceModal();
    if (store.activeSubentryId === subId) {
      store.activeSubentryId = "";
      store.deviceSelected = false;
      store.currentScope = "device";
      store.currentViewId = "select_device_prompt";
      store.syncUrl(true);
    }
    if (res) store.ingestPayload(res, false);
    store.showToast("Removed Device from Latter");
  } catch (err) {
    store.removeModal = { ...store.removeModal, busy: false };
    store.showToast(formatWsError(err, "Could not remove Device"), true);
    store.host.requestUpdate();
  }
}
async function confirmResetDeviceOp(store) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  if (!store.resetModal.deviceSettings && !store.resetModal.latterOptions) return;
  store.resetModal = { ...store.resetModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.resetDevice({
      subentryId: targetSubentryId,
      deviceSettings: store.resetModal.deviceSettings,
      latterOptions: store.resetModal.latterOptions,
    });
    store.closeResetDeviceModal();
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast("Reset Device to defaults");
  } catch (err) {
    store.resetModal = { ...store.resetModal, busy: false };
    store.showToast(formatWsError(err, "Could not reset Device"), true);
    store.host.requestUpdate();
  }
}
function selectBleCandidateInModalOp(store, addr) {
  const cand = (store.state?.discovered_ble_devices || []).find(
    (c) => (c.target_address || c.address) === addr,
  );
  const candAddr = cand ? cand.target_address || cand.address || addr : addr;
  const candTitle = cand ? cand.title || cand.name || "" : "";
  store.addBleModal = {
    ...store.addBleModal,
    candidateAddr: addr,
    address: cand ? candAddr : store.addBleModal.address,
    name: candTitle || store.addBleModal.name,
  };
  store.host.requestUpdate();
}
async function quickAdoptBleCandidateOp(
  store,
  title,
  targetAddress,
  assignedPerson = "",
) {
  if (!title || !targetAddress) return;
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name: title,
        target_address: targetAddress,
        assigned_person: assignedPerson,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${title}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
  }
}
async function confirmAddBleModalOp(store) {
  const name = store.addBleModal.name.trim();
  const targetAddress = store.addBleModal.address.trim();
  if (!name || !targetAddress) {
    store.showToast("Enter both a name and a Bluetooth address or entity", true);
    return;
  }
  store.addBleModal = { ...store.addBleModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name,
        target_address: targetAddress,
        assigned_person: store.addBleModal.assignedPerson,
      },
      store.activeSubentryId || null,
    );
    store.closeAddBleModal();
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${name}"`);
  } catch (err) {
    store.addBleModal = { ...store.addBleModal, busy: false };
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
    store.host.requestUpdate();
  }
}
async function checkSystemUpdatesOp(store) {
  store.showToast("Checking firmware updates…");
  try {
    const res = await store.ws.runSystemCommand(
      "check_system_updates",
      {},
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
      const info = res.update_check;
      if (info) {
        store.showToast(
          info.available > 0
            ? `${info.available} firmware update(s) available across ${info.checked} checked Device(s)`
            : `Checked ${info.checked} Device(s) — all firmware is up to date`,
        );
        return;
      }
    }
    store.showToast("Firmware update check finished");
  } catch (err) {
    store.showToast(formatWsError(err, "Firmware update check failed"), true);
  }
}
async function sendAnnouncementOp(store) {
  const message = store.announceMessage.trim();
  if (!message) {
    store.showToast("Enter a message", true);
    return;
  }
  const payload = {
    mode: store.announceMode,
    target_device: store.announceTarget || "all",
    message,
  };
  if (store.announceMode === "notify") {
    const title = store.announceTitle.trim();
    if (!title) {
      store.showToast("Enter a notification title", true);
      return;
    }
    payload.title = title;
    payload.priority = store.announcePriority;
    payload.include_camera = store.announceIncludeCamera;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "send_announcement",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast(
      store.announceMode === "notify" ? "Sent notification" : "Broadcast announcement sent",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not send announcement"), true);
  }
}
async function exportBackupOp(store, explicitSubentryId) {
  try {
    const dateStr = new Date().toISOString().slice(0, 10);
    if (explicitSubentryId) {
      const { bundle } = await store.ws.exportBackup("device", explicitSubentryId);
      const slug = String(bundle.target_device || store.state?.config?.device_slug || "esphome");
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
      return;
    }
    const choice = store.backupExportScope || "system";
    const deviceId = choice.startsWith("device:") ? choice.slice(7) : choice !== "system" ? choice : "";
    if (!deviceId) {
      const { bundle } = await store.ws.exportBackup("system");
      triggerJsonDownload(`latter-system-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the System backup");
    } else {
      const { bundle } = await store.ws.exportBackup("device", deviceId);
      const slug = String(bundle.target_device || deviceId);
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Backup export failed"), true);
  }
}
async function restoreFromUploadedFileOp(store) {
  if (!store.selectedBackupFile) {
    store.showToast("Choose a JSON backup file first", true);
    return;
  }
  try {
    const text = await store.selectedBackupFile.text();
    const raw = JSON.parse(text);
    const bundle =
      raw.bundle && typeof raw.bundle === "object" ? (raw.bundle) : raw;
    const scope = String(bundle.scope || "") === "device" ? "device" : "system";
    const targetId = scope === "device" ? store.backupRestoreSubentryId || "" : "";
    if (scope === "device" && !targetId) {
      store.showToast("Choose the Device to restore this Device backup onto", true);
      return;
    }
    const res = await store.ws.importBackup({
      scope,
      bundle,
      targetSubentryId: targetId || null,
      selectedSubentryId: store.activeSubentryId || null,
      restoreEspHomeEntities: store.backupRestoreEsp,
    });
    store.selectedBackupFile = null;
    if (res) store.ingestPayload(res, false);
    store.showToast(scope === "device" ? "Restored the Device backup" : "Restored the System backup");
  } catch (err) {
    store.showToast(formatWsError(err, "Backup restore failed"), true);
  }
}
function formatVisibleLogsOp(store) {
  const entries = store.state?.internal_logs || [];
  const filter = store.logFilter || "all";
  const filtered = entries.filter((e) => {
    const lvl = String(e.level || "").toUpperCase();
    const src = String(e.source || "").toLowerCase();
    if (filter === "latter") return src === "studio" || src === "system" || src.includes("latter");
    if (filter === "errors") return lvl === "WARNING" || lvl === "WARN" || lvl === "ERROR" || lvl === "CRITICAL";
    if (filter.startsWith("device:") || filter.startsWith("dev:")) {
      const slug = (filter.startsWith("device:") ? filter.slice(7) : filter.slice(4)).toLowerCase();
      return src === slug || String(e.message || "").toLowerCase().includes(slug);
    }
    return true;
  });
  if (!filtered.length) return "No events logged yet.";
  return filtered
    .map((e) => {
      const rawTs = e.timestamp ?? e.ts ?? "";
      const formattedTs = rawTs !== "" ? fmtDateTime(rawTs, store.hass) : "";
      const lvl = String(e.level || "INFO").toUpperCase();
      const src = String(e.source || "latter");
      return `${formattedTs ? `[${formattedTs}] ` : ""}${lvl} (${src}): ${String(e.message || "")}`;
    })
    .join("\n");
}
async function copyLogsToClipboardOp(store) {
  const ok = await copyTextToClipboard(formatVisibleLogsOp(store));
  store.showToast(ok ? "Copied logs to clipboard" : "Could not copy logs", !ok);
}
async function clearInternalLogsOp(store) {
  try {
    const res = await store.ws.runSystemCommand(
      "clear_internal_logs",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, true);
    store.showToast("Cleared internal logs");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear logs"), true);
  }
}

// --- src/state/entity-config-ops.ts ---
/**
 * Device & System configuration staging, optimistic ESPHome entity actions,
 * dock/activity/wallpaper/color mutations, and shared-entity list editors.
 */
const SAVE_DEBOUNCE_MS = 220;
const ENTITY_OPTIMISTIC_TTL_MS = 8000;
const PENDING_ENTITY_STATES = new Map();
const POWER_PROFILE_PREFS = {
  "Portable Carry": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Docked Only",
    pickup_to_wake: "Docked Only",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Handheld Roaming": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Always On",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "30 min",
    docked_screensaver: true,
  },
  "Wearable Watch": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Always On",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "15s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Tabletop Dock": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Docked Only",
    pickup_to_wake: "Disabled",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "5 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Always-On Wall / Desk": {
    wake_word_mode: "Always On",
    tap_to_wake: "Always On",
    pickup_to_wake: "Disabled",
    battery_screen_timeout: "Never",
    docked_idle_timeout: "5 min",
    battery_hibernate_timeout: "Disabled",
    docked_screensaver: true,
  },
};
const POWER_PROFILE_SUBKEYS = new Set ([
  "wake_word_mode",
  "tap_to_wake",
  "pickup_to_wake",
  "battery_screen_timeout",
  "docked_idle_timeout",
  "battery_hibernate_timeout",
  "docked_screensaver",
]);
function expandDevicePrefPatch(
  currentCfg,
  rawPatch,
) {
  const expanded = { ...rawPatch };
  if (typeof rawPatch.power_profile === "string" && rawPatch.power_profile in POWER_PROFILE_PREFS) {
    const preset = POWER_PROFILE_PREFS[rawPatch.power_profile];
    for (const [k, v] of Object.entries(preset)) {
      if (!(k in rawPatch)) {
        expanded[k] = v;
      }
    }
  } else if (
    !("power_profile" in rawPatch) &&
    Object.keys(rawPatch).some((k) => POWER_PROFILE_SUBKEYS.has(k))
  ) {
    const curProf = String(currentCfg.power_profile || "Portable Carry");
    const preset = POWER_PROFILE_PREFS[curProf];
    if (preset) {
      const merged = { ...currentCfg, ...rawPatch };
      for (const [k, want] of Object.entries(preset)) {
        const have = merged[k] !== undefined ? merged[k] : want;
        if (have !== want) {
          expanded.power_profile = "Custom";
          break;
        }
      }
    }
  }
  return expanded;
}
function overlayDevicePrefsOnSections(
  payload,
  rawPatch,
) {
  if (!rawPatch || Object.keys(rawPatch).length === 0) return;
  const curCfg = (payload.config || {});
  const expanded = expandDevicePrefPatch(curCfg, rawPatch);
  payload.config = {
    ...payload.config,
    ...expanded,
  };
  const sections = payload?.esphome?.sections;
  if (!sections) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        if (item.pref_key && item.pref_key in expanded) {
          const val = expanded[item.pref_key];
          const nextState = item.domain === "switch" ? (val ? "on" : "off") : String(val ?? "");
          return { ...item, state: nextState };
        }
        if (
          "volume_step_size" in expanded &&
          item.domain === "number" &&
          item.entity_id.startsWith("media_player.")
        ) {
          const stepNum = Number(expanded.volume_step_size);
          if (Number.isFinite(stepNum) && stepNum > 0) {
            return { ...item, step: stepNum };
          }
        }
        return item;
      }),
    })),
  };
}
function overlayPendingEntityStates(
  payload,
  pendingMap = PENDING_ENTITY_STATES,
) {
  const now = Date.now();
  for (const [eid, entry] of pendingMap.entries()) {
    if (entry.expires <= now) {
      pendingMap.delete(eid);
    }
  }
  const sections = payload?.esphome?.sections;
  if (!sections || pendingMap.size === 0) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        const pending = pendingMap.get(item.entity_id);
        if (!pending) return item;
        const curState = String(item.state ?? "");
        const sameNumeric =
          curState !== "" &&
          pending.state !== "" &&
          Number.isFinite(Number(curState)) &&
          Number.isFinite(Number(pending.state)) &&
          Number(curState) === Number(pending.state);
        if (curState === pending.state || sameNumeric) {
          pendingMap.delete(item.entity_id);
          return item;
        }
        return { ...item, state: pending.state };
      }),
    })),
  };
}
async function commitEntityChange(
  store,
  entityId,
  optimisticState,
  body,
  errorPrefix,
) {
  return store.executeEntityAction(entityId, optimisticState, body, errorPrefix);
}
function stageDeviceSettingOp(
  store,
  key,
  value,
  controlDomId,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  let bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) {
    bucket = {
      targetSubentryId,
      patch: {},
      previousValues: {},
      timer: null,
    };
    store.pendingDeviceBuckets.set(targetSubentryId, bucket);
  }
  const curCfg =
    store.state && store.state.subentry_id === targetSubentryId
      ? ((store.state.config || {}))
      : {};
  const snapshotKey = (k) => {
    if (!(k in bucket.previousValues)) {
      bucket.previousValues[k] = curCfg[k];
    }
  };
  snapshotKey(key);
  if (key === "power_profile" || POWER_PROFILE_SUBKEYS.has(key)) {
    snapshotKey("power_profile");
    for (const sk of POWER_PROFILE_SUBKEYS) {
      snapshotKey(sk);
    }
  }
  if (controlDomId) {
    bucket.previousValues[`__dom:${controlDomId}`] = bucket.previousValues[key];
  }
  bucket.patch[key] = value;
  if (store.state) {
    const nextSystemDevices =
      key === "device_remote_group" && Array.isArray(store.state.system_devices)
        ? store.state.system_devices.map((d) =>
            d.subentry_id === targetSubentryId
              ? { ...d, device_remote_group: String(value || "area_auto") }
              : d,
          )
        : store.state.system_devices;
    if (store.state.subentry_id === targetSubentryId) {
      const nextPayload = {
        ...store.state,
        system_devices: nextSystemDevices,
        config: { ...store.state.config },
      };
      overlayDevicePrefsOnSections(nextPayload, { [key]: value });
      store.state = nextPayload;
    } else if (nextSystemDevices !== store.state.system_devices) {
      store.state = {
        ...store.state,
        system_devices: nextSystemDevices,
      };
    }
  }
  if (bucket.timer) clearTimeout(bucket.timer);
  bucket.timer = setTimeout(() => {
    void store.flushDeviceBucket(targetSubentryId);
  }, SAVE_DEBOUNCE_MS);
  store.host.requestUpdate();
}
async function flushDeviceBucketOp(store, targetSubentryId) {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) return;
  if (bucket.timer) {
    clearTimeout(bucket.timer);
    bucket.timer = null;
  }
  const patch = { ...bucket.patch };
  const previousValues = { ...bucket.previousValues };
  store.pendingDeviceBuckets.delete(targetSubentryId);
  if (Object.keys(patch).length === 0) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: patch,
    });
    if (res) {
      if (store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      } else if (store.state && Array.isArray(res.system_devices)) {
        store.state = {
          ...store.state,
          system_devices: res.system_devices,
          issues: res.issues ?? store.state.issues,
        };
        store.host.requestUpdate();
      }
    }
    store.showToast("Saved");
  } catch (err) {
    const controlRevert = {};
    for (const [k, v] of Object.entries(previousValues)) {
      if (k.startsWith("__dom:")) {
        const domId = k.slice(6);
        if (typeof v === "boolean") controlRevert[domId] = v;
        else if (v !== undefined && v !== null) controlRevert[domId] = String(v);
        else controlRevert[domId] = "";
      }
    }
    if (store.state) {
      const nextSystemDevices =
        "device_remote_group" in previousValues && Array.isArray(store.state.system_devices)
          ? store.state.system_devices.map((d) =>
              d.subentry_id === targetSubentryId
                ? {
                    ...d,
                    device_remote_group: String(previousValues.device_remote_group || "area_auto"),
                  }
                : d,
            )
          : store.state.system_devices;
      if (store.state.subentry_id === targetSubentryId) {
        const restoredConfig = {
          ...(store.state.config),
        };
        const restoredPrefs = {};
        for (const [k, v] of Object.entries(previousValues)) {
          if (!k.startsWith("__dom:")) {
            restoredConfig[k] = v;
            if (v !== undefined) {
              restoredPrefs[k] = v;
            }
          }
        }
        const nextPayload = {
          ...store.state,
          system_devices: nextSystemDevices,
          config: restoredConfig,
        };
        if (Object.keys(restoredPrefs).length > 0) {
          overlayDevicePrefsOnSections(nextPayload, restoredPrefs);
        }
        store.state = nextPayload;
      } else if (nextSystemDevices !== store.state.system_devices) {
        store.state = {
          ...store.state,
          system_devices: nextSystemDevices,
        };
      }
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save Device settings"), true);
    store.host.requestUpdate();
  }
}
function stageSystemSettingOp(
  store,
  key,
  value,
  controlDomId,
) {
  if (!(key in store.pendingSystemPrevious)) {
    const prev = (store.state?.system_config)?.[key];
    store.pendingSystemPrevious[key] = prev !== undefined ? structuredClone(prev) : undefined;
  }
  if (controlDomId && !(`__dom:${controlDomId}` in store.pendingSystemPrevious)) {
    const prevScalar = store.pendingSystemPrevious[key];
    if (typeof prevScalar === "string" || typeof prevScalar === "number" || typeof prevScalar === "boolean") {
      store.pendingSystemPrevious[`__dom:${controlDomId}`] = prevScalar;
    }
  }
  store.pendingSystemPatch[key] = value;
  if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: value,
      },
    };
  }
  if (store.systemSaveTimer) clearTimeout(store.systemSaveTimer);
  store.systemSaveTimer = setTimeout(() => {
    void store.flushSystemSettings();
  }, SAVE_DEBOUNCE_MS);
  store.host.requestUpdate();
}
async function flushSystemSettingsOp(store) {
  if (store.systemSaveTimer) {
    clearTimeout(store.systemSaveTimer);
    store.systemSaveTimer = null;
  }
  const patch = { ...store.pendingSystemPatch };
  const previousValues = { ...store.pendingSystemPrevious };
  store.pendingSystemPatch = {};
  store.pendingSystemPrevious = {};
  if (Object.keys(patch).length === 0) return;
  try {
    const res = await store.ws.runSystemCommand(
      "save_system_config",
      { config: patch },
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
    }
    store.showToast("Saved System settings");
  } catch (err) {
    const controlRevert = {};
    if (store.state?.system_config) {
      const restored = {
        ...(store.state.system_config),
      };
      for (const [k, v] of Object.entries(previousValues)) {
        if (k.startsWith("__dom:")) {
          const domId = k.slice(6);
          controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
        } else if (v !== undefined) {
          restored[k] = v;
        }
      }
      store.state = {
        ...store.state,
        system_config: restored,
      };
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save System settings"), true);
    store.host.requestUpdate();
  }
}
function currentEntityState(store, entityId) {
  for (const sec of store.state?.esphome?.sections || []) {
    for (const it of sec.items || []) {
      if (it.entity_id === entityId) return it.state;
    }
  }
  return "";
}
function applyOptimisticEntity(store, entityId, nextState) {
  const prev = currentEntityState(store, entityId);
  store.pendingEntityStates.set(entityId, {
    state: nextState,
    previousValue: prev,
    expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
  });
  if (store.state?.esphome?.sections) {
    const nextPayload = { ...store.state };
    overlayPendingEntityStates(nextPayload, store.pendingEntityStates);
    store.state = nextPayload;
    store.host.requestUpdate();
  }
  return prev;
}
function rollbackOptimisticEntity(store, entityId, prev) {
  store.pendingEntityStates.delete(entityId);
  if (store.state?.esphome?.sections) {
    store.state = {
      ...store.state,
      esphome: {
        ...store.state.esphome,
        sections: store.state.esphome.sections.map((sec) => ({
          ...sec,
          items: (sec.items || []).map((it) => (it.entity_id === entityId ? { ...it, state: prev } : it)),
        })),
      },
    };
  }
  store.host.requestUpdate();
}
async function executeEntityActionOp(
  store,
  entityId,
  optimisticState,
  body,
  errorPrefix,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !entityId) return false;
  const prev = optimisticState !== undefined ? applyOptimisticEntity(store, entityId, optimisticState) : "";
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
      entity_id: entityId,
      ...body,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    return true;
  } catch (err) {
    if (optimisticState !== undefined) rollbackOptimisticEntity(store, entityId, prev);
    store.showToast(formatWsError(err, errorPrefix), true);
    return false;
  }
}
async function runDeviceActionOp(
  store,
  action,
  toastMessage,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !action) return false;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "device_action", {
      action,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    if (toastMessage) {
      store.showToast(toastMessage);
    }
    return true;
  } catch (err) {
    store.showToast(formatWsError(err, "Device action failed"), true);
    return false;
  }
}
function getEnabledDockTokensOp(store) {
  const raw = String(store.state?.config?.dock_apps ?? "");
  if (!raw.trim()) {
    return DOCK_APPS_CATALOG.map((a) => a.token);
  }
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
function toggleDockAppTokenOp(store, appId) {
  const current = getEnabledDockTokensOp(store);
  const idx = current.indexOf(appId);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Dock app enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(appId);
  }
  store.stageDeviceSetting("dock_apps", current.join(","));
}
function moveDockAppTokenOp(store, appId, delta) {
  const current = getEnabledDockTokensOp(store);
  const idx = current.indexOf(appId);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("dock_apps", current.join(","));
}
function getEnabledAreaCategoriesOp(store) {
  const raw = String(store.state?.config?.area_categories ?? "");
  if (!raw.trim()) {
    return [...DEFAULT_AREA_CATEGORIES_TOKENS];
  }
  const known = new Set(AREA_CATEGORIES_CATALOG.map((c) => c.token));
  const parsed = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s, i, arr) => Boolean(s) && known.has(s) && arr.indexOf(s) === i);
  return parsed.length > 0 ? parsed : [...DEFAULT_AREA_CATEGORIES_TOKENS];
}
function toggleAreaCategoryTokenOp(store, token) {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Area category enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(token);
  }
  store.stageDeviceSetting("area_categories", current.join(","));
}
function moveAreaCategoryTokenOp(store, token, delta) {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("area_categories", current.join(","));
}
function getEnabledActivitySourcesOp(store) {
  const rawCfg = store.state?.config?.activity_sources;
  if (rawCfg === undefined || rawCfg === null) {
    return ACTIVITY_SOURCES_CATALOG.map((s) => s.id);
  }
  return String(rawCfg)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
function toggleActivitySourceOp(store, sourceId) {
  const current = getEnabledActivitySourcesOp(store);
  const idx = current.indexOf(sourceId);
  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(sourceId);
  }
  store.stageDeviceSetting("activity_sources", current.join(","));
}
function applyDeviceCustomColorOp(
  store,
  hex,
  switchColorProfile = true,
) {
  if (!isValidHexColor(hex)) return;
  store.stageDeviceSetting("device_custom_color", hex.toUpperCase());
  if (switchColorProfile) {
    for (const sec of store.state?.esphome?.sections || []) {
      for (const it of sec.items || []) {
        if (
          it.domain === "select" &&
          (it.name || "").toLowerCase().includes("color profile") &&
          (it.options || []).includes("Custom") &&
          it.state !== "Custom"
        ) {
          if (it.pref_key) {
            store.stageDeviceSetting(it.pref_key, "Custom");
          } else {
            void store.espSelect(it.entity_id, "Custom");
          }
        }
      }
    }
  }
}
function deleteCustomPaletteOp(store, hex) {
  const target = hex.toUpperCase();
  const next = (store.state?.system_config?.custom_palettes || []).filter(
    (p) => p.hex.toUpperCase() !== target,
  );
  store.stageSystemSetting("custom_palettes", next);
}
async function uploadWallpaperOp(store, scope) {
  const file = scope === "device" ? store.selectedDeviceWallpaperFile : store.selectedSystemWallpaperFile;
  if (!file) {
    store.showToast("Choose an image file first", true);
    return;
  }
  const targetSubentryId = scope === "device" ? store.activeSubentryId : undefined;
  if (scope === "device" && !targetSubentryId) {
    store.showToast("Choose a Device first", true);
    return;
  }
  store.uploadScope = scope;
  store.uploadBusy = true;
  store.uploadPercent = 0;
  store.host.requestUpdate();
  try {
    const result = await store.ws.uploadWallpaperMultipart({
      scope,
      subentryId: targetSubentryId,
      file,
      onProgress: (pct) => {
        store.uploadPercent = pct;
        store.host.requestUpdate();
      },
    });
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = null;
    } else {
      store.selectedSystemWallpaperFile = null;
    }
    const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
    store.pendingDomRevert = {
      controlIds: { ...(store.pendingDomRevert?.controlIds || {}), [inputId]: "" },
    };
    if (store.state) {
      if (result.wallpapers && scope === "device" && store.activeSubentryId === targetSubentryId) {
        store.state = { ...store.state, wallpapers: result.wallpapers };
      }
      if (result.system_wallpapers) {
        store.state = { ...store.state, system_wallpapers: result.system_wallpapers };
      }
    }
    await store.refreshState();
    store.showToast("Uploaded wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Wallpaper upload failed"), true);
  } finally {
    store.uploadBusy = false;
    store.uploadScope = null;
    store.uploadPercent = 0;
    store.host.requestUpdate();
  }
}
function clearPendingWallpaperCycle(store, targetSubentryId) {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket || !("wallpaper_cycle_minutes" in bucket.patch)) return;
  delete bucket.patch.wallpaper_cycle_minutes;
  delete bucket.previousValues.wallpaper_cycle_minutes;
  delete bucket.previousValues["__dom:cfg-wallpaper_cycle_minutes"];
  if (Object.keys(bucket.patch).length === 0) {
    if (bucket.timer) clearTimeout(bucket.timer);
    store.pendingDeviceBuckets.delete(targetSubentryId);
  }
}
async function selectWallpaperSourceOp(store, sourceId) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  clearPendingWallpaperCycle(store, targetSubentryId);
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "select_wallpaper", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(sourceId ? "Wallpaper applied" : "Wallpaper turned off");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not select wallpaper"), true);
  }
}
async function setWallpaperRotationOp(store, minutes) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
  clearPendingWallpaperCycle(store, targetSubentryId);
  const prevMins =
    store.state && store.state.subentry_id === targetSubentryId
      ? Number(store.state.config?.wallpaper_cycle_minutes || 0)
      : 0;
  if (store.state && store.state.subentry_id === targetSubentryId) {
    store.state = {
      ...store.state,
      config: {
        ...store.state.config,
        wallpaper_cycle_minutes: cleanMins,
      },
    };
    store.host.requestUpdate();
  }
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: { wallpaper_cycle_minutes: cleanMins },
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(cleanMins > 0 ? "Wallpaper rotation enabled" : "Wallpaper rotation stopped");
  } catch (err) {
    if (store.state && store.state.subentry_id === targetSubentryId) {
      store.state = {
        ...store.state,
        config: {
          ...store.state.config,
          wallpaper_cycle_minutes: prevMins,
        },
      };
      store.pendingDomRevert = {
        controlIds: {
          ...(store.pendingDomRevert?.controlIds || {}),
          "cfg-wallpaper_cycle_minutes": String(prevMins),
        },
      };
      store.host.requestUpdate();
    }
    store.showToast(formatWsError(err, "Could not update wallpaper rotation"), true);
  }
}
async function toggleWallpaperFavOp(store, sourceId) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorite"), true);
  }
}
async function setAllWallpaperFavoritesOp(
  store,
  sourceIds,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_ids: [...sourceIds],
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(
      sourceIds.length > 0 ? "Starred all wallpapers" : "Cleared starred wallpapers",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorites"), true);
  }
}
async function deleteWallpaperOp(
  store,
  scope,
  sourceId,
) {
  try {
    if (scope === "device") {
      const targetSubentryId = store.activeSubentryId;
      if (!targetSubentryId) return;
      const res = await store.ws.runDeviceCommand(targetSubentryId, "delete_wallpaper", {
        source_id: sourceId,
      });
      if (res && store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      }
    } else {
      const res = await store.ws.runSystemCommand(
        "delete_system_wallpaper",
        { source_id: sourceId },
        store.activeSubentryId || null,
      );
      if (res) store.ingestPayload(res, false);
    }
    store.showToast("Deleted wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete wallpaper"), true);
  }
}
function updateStringListRowOp(
  store,
  key,
  index,
  value,
) {
  const list = [...(store.state?.system_config?.[key] || [])];
  list[index] = value;
  store.stageSystemSetting(key, list);
}
function addStringListRowOp(
  store,
  key,
  defaultEntity = "",
  maxLen = 10,
) {
  const list = [...(store.state?.system_config?.[key] || [])];
  if (list.length >= maxLen) {
    store.showToast(`Maximum of ${maxLen} entries reached`, true);
    return;
  }
  list.push(defaultEntity);
  store.stageSystemSetting(key, list);
}
function removeStringListRowOp(
  store,
  key,
  index,
) {
  const list = [...(store.state?.system_config?.[key] || [])];
  list.splice(index, 1);
  store.stageSystemSetting(key, list);
}
function addVolumeOverrideRowOp(store) {
  const list = [...(store.state?.system_config?.volume_overrides || [])];
  if (list.length >= 10) {
    store.showToast("Maximum of 10 volume overrides reached", true);
    return;
  }
  const speakers = store.state?.catalog?.ma_speakers || [];
  const targets = store.state?.catalog?.volume_targets || store.state?.catalog?.remotes || [];
  list.push({
    speaker: speakers[0]?.id || "",
    target: targets[0]?.id || speakers[0]?.id || "",
  });
  store.stageSystemSetting("volume_overrides", list);
}
function updateVolumeOverrideRowOp(
  store,
  index,
  field,
  value,
) {
  const list = (store.state?.system_config?.volume_overrides || []).map((v) => ({
    ...v,
  }));
  if (!list[index]) return;
  list[index][field] = value;
  store.stageSystemSetting("volume_overrides", list);
}
function removeVolumeOverrideRowOp(store, index) {
  const list = [...(store.state?.system_config?.volume_overrides || [])];
  list.splice(index, 1);
  store.stageSystemSetting("volume_overrides", list);
}
function addRemoteGroupRowOp(store) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) => ({
    ...g,
    remotes: [...(g.remotes || [])],
  }));
  const id = `group_${Date.now().toString(36)}`;
  groups.push({ id, name: "New Remote Group", area_id: "", remotes: [] });
  store.stageSystemSetting("remote_groups", groups);
}
function updateRemoteGroupFieldOp(
  store,
  groupId,
  field,
  value,
) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) =>
    g.id === groupId ? { ...g, [field]: value } : { ...g, remotes: [...(g.remotes || [])] },
  );
  store.stageSystemSetting("remote_groups", groups);
}
function toggleRemoteInGroupOp(
  store,
  groupId,
  remoteEntity,
) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) => {
    if (g.id !== groupId) return { ...g, remotes: [...(g.remotes || [])] };
    const remotes = [...(g.remotes || [])];
    const idx = remotes.indexOf(remoteEntity);
    if (idx >= 0) remotes.splice(idx, 1);
    else remotes.push(remoteEntity);
    return { ...g, remotes };
  });
  store.stageSystemSetting("remote_groups", groups);
}
function removeRemoteGroupRowOp(store, groupId) {
  const groups = (store.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
  store.stageSystemSetting("remote_groups", groups);
}
async function previewCameraOp(
  store,
  cameraEntity,
  bustCache = false,
) {
  if (!cameraEntity) {
    store.closeCameraPreview();
    return;
  }
  const dbObj = (store.state?.doorbells || []).find((b) => b.camera_entity === cameraEntity);
  const camObj = (store.state?.catalog?.cameras || []).find((c) => c.id === cameraEntity);
  const existingSigned = dbObj?.preview_url || camObj?.preview_url || "";
  if (existingSigned) {
    const sep = existingSigned.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = bustCache ? `${existingSigned}${sep}_ts=${Date.now()}` : existingSigned;
    store.host.requestUpdate();
    return;
  }
  try {
    const signed = await store.ws.signHaPath(
      `/api/camera_proxy/${encodeURIComponent(cameraEntity)}`,
      300,
    );
    const sep = signed.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = `${signed}${sep}_ts=${Date.now()}`;
    store.host.requestUpdate();
  } catch (err) {
    store.showToast(formatWsError(err, "Add a Latter Device to preview cameras"), true);
  }
}
async function testDoorbellSpeakerOp(store) {
  const cams = store.state?.system_config?.camera_entities || [];
  if (!cams[0]) {
    store.showToast("Add a camera in Shared Entities first", true);
    return;
  }
  if (!store.doorbellTestSubentryId) {
    store.showToast("Choose a Device to test from", true);
    return;
  }
  await store.flushSystemSettings();
  try {
    const res = await store.ws.runSystemCommand(
      "test_doorbell_speaker",
      {
        subentry_id: store.doorbellTestSubentryId,
        camera_entity: cams[0],
        message: "Testing Latter doorbell audio.",
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Played test message on door speaker");
  } catch (err) {
    store.showToast(formatWsError(err, "Door speaker test failed"), true);
  }
}

// --- src/state/groups-presence-ops.ts ---
/**
 * Device Groups, bulk ESPHome control actions, BLE calibration, and Area sensor fusion operations.
 */
async function createDeviceGroupOp(store) {
  const name = store.newGroupName.trim();
  const description = store.newGroupDesc.trim();
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      { name, description },
      store.activeSubentryId || null,
    );
    store.newGroupName = "";
    store.newGroupDesc = "";
    if (res) store.ingestPayload(res, false);
    store.showToast(`Created group "${name}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not create Device Group"), true);
  }
}
async function deleteDeviceGroupOp(store, groupId) {
  try {
    const res = await store.ws.runSystemCommand(
      "delete_device_group",
      { group_id: groupId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Deleted Device Group");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete Device Group"), true);
  }
}
async function syncDeviceGroupOp(
  store,
  groupId,
  singleSubentryId,
) {
  try {
    const payload = { group_id: groupId };
    if (singleSubentryId) payload.subentry_id = singleSubentryId;
    const res = await store.ws.runSystemCommand(
      "sync_device_group",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Synced to group baseline");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not sync Device Group"), true);
  }
}
async function seedGroupBaselineFromDeviceOp(store) {
  if (!store.seedGroupTargetId || !store.seedSourceSubentryId) {
    store.showToast("Choose both a target group and a source Device", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "seed_group_baseline",
      {
        group_id: store.seedGroupTargetId,
        subentry_id: store.seedSourceSubentryId,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Saved group baseline from Device");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not seed group baseline"), true);
  }
}
function resolvedGroupCtrlIdOp(store) {
  const filter = store.groupCtrlFilter || "all";
  if (filter.startsWith("group:")) return filter.slice(6);
  if (filter === "trait:roaming") return "roaming";
  if (filter === "trait:stationary") return "stationary";
  return filter;
}
async function setGroupDeviceSettingOp(
  store,
  patch,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "set_group_device_setting",
      {
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Applied group setting");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not apply group setting"), true);
  }
}
function filteredControlTargetsOp(store, ctrl) {
  const grpId = resolvedGroupCtrlIdOp(store);
  return (ctrl.targets || [])
    .filter((t) => {
      if (grpId === "all") return true;
      if (grpId === "roaming") return Boolean(t.is_roaming);
      if (grpId === "stationary") return !t.is_roaming;
      return t.device_group === grpId;
    })
    .map((t) => t.entity_id)
    .filter(Boolean);
}
async function bulkToggleOp(
  store,
  ctrl,
  turnOn,
) {
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: turnOn });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        action: turnOn ? "turn_on" : "turn_off",
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk switch update failed"), true);
  }
}
async function bulkSelectOp(
  store,
  ctrl,
  option,
) {
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: option });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        option,
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk option update failed"), true);
  }
}
async function bulkNumberOp(
  store,
  ctrl,
  level,
) {
  if (!Number.isFinite(level)) return;
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: level });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        level,
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk number update failed"), true);
  }
}
function getActiveSurveyDeviceOp(store) {
  const devs = store.state?.system_devices || [];
  return devs.find((d) => d.subentry_id === store.bleSurveySubentryId);
}
async function setBleOffsetOp(
  store,
  areaId,
  offsetDb,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "set_ble_area_offset",
      { area_id: areaId, offset_db: offsetDb },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update BLE offset"), true);
  }
}
async function autoCalibrateHereOp(store, areaId) {
  if (!store.bleSurveySubentryId) {
    store.showToast("Select a calibration Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "auto_calibrate_here",
      { area_id: areaId, survey_subentry_id: store.bleSurveySubentryId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Calibrated Area offset");
  } catch (err) {
    store.showToast(formatWsError(err, "Calibration failed"), true);
  }
}
async function setAreaFusionOp(
  store,
  areaId,
  update,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "set_area_fusion",
      { area_id: areaId, ...update },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update Area fusion"), true);
  }
}

// --- src/state/store.ts ---
/**
 * Encapsulated Reactive Store for Latter Studio (`StudioStore`).
 *
 * Key invariants:
 * - Zero `window.*` globals: each `<latter-studio>` element owns its `StudioStore` controller.
 * - Snapshot-isolated pending edits: `stageDeviceSetting` captures `targetSubentryId` at input time,
 *   so switching Devices or routes flushes pending edits strictly to Device A (`previousSubentryId`)
 *   before loading Device B, and rolls back cleanly on error even if the input retains focus.
 * - Streams `ble_survey_delta` over the WebSocket subscription without 1.5s full-state polling.
 * - Requests `include_logs: true` ONLY when System -> Tools -> System & Device Logs is open.
 */
function slugToView (map, slug) {
  const cleaned = String(slug || "").trim().toLowerCase();
  for (const [viewId, s] of Object.entries(map)) {
    if (s === cleaned) return viewId;
  }
  return null;
}
class StudioStore {
           host;
           ws;
  // Core navigation & lifecycle state (D-001: starts on Devices landing list)
  currentScope = "device";
  currentViewId = "select_device_prompt";
  activeSubentryId = "";
  deviceSelected = false;
  state = null;
  loading = true;
  loadError = "";
  studioRevMismatch = false;
  // Toast feedback
  toastMessage = "";
  toastIsError = false;
          toastTimer = null;
  // Upload state (`XMLHttpRequest` multipart <= 15 MB)
  uploadScope = null;
  uploadBusy = false;
  uploadPercent = 0;
  selectedDeviceWallpaperFile = null;
  selectedSystemWallpaperFile = null;
  selectedBackupFile = null;
  // Devices table UI state
  deviceSortField = "title";
  deviceSortAsc = true;
  deviceCategoryFilter = "all";
  // Device Security state
  devicePinDraft = "";
  systemPinDraft = "";
  pinBusy = false;
  // System Shared Entities UI state
  doorbellTestSubentryId = "";
  activeCameraPreviewEntity = "";
  cameraPreviewUrl = "";
  // System Device Groups UI state
  newGroupName = "";
  newGroupDesc = "";
  seedGroupTargetId = "";
  seedSourceSubentryId = "";
  groupCtrlFilter = "all";
  groupCtrlCategoryFilter = "all";
  // System BLE & Area Presence UI state
  bleSurveySubentryId = "";
  bleLiveStreamActive = true;
           openFusionAreas = new Set();
  // System Tools UI state
  announceMode = "notify";
  announceTarget = "all";
  announceTitle = "";
  announceMessage = "";
  announcePriority = "normal";
  announceIncludeCamera = false;
  backupExportScope = "system";
  backupRestoreSubentryId = "";
  backupRestoreEsp = true;
  logsOpen = false;
  logFilter = "all";
  // Modal states
  removeModal = { open: false, subentryId: "", title: "", busy: false };
  resetModal = { open: false, deviceSettings: true, latterOptions: true, busy: false };
  addBleModal = {
    open: false,
    candidateAddr: "",
    name: "",
    address: "",
    assignedPerson: "",
    busy: false,
  };
  colorWheelModal = {
    open: false,
    targetScope: "system",
    hex: "",
    name: "",
    busy: false,
  };
  pendingScrollCardId = "";
  pendingDomRevert = null;
  // Snapshot-isolated pending settings queues (shared with `state/*-ops.ts`)
  pendingSystemPatch = {};
  pendingSystemPrevious = {};
  systemSaveTimer = null;
           pendingDeviceBuckets = new Map();
           pendingEntityStates = new Map();
  // Subscription management
          subGen = 0;
          wsUnsub = null;
          subscribedKey = "";
          fallbackPollTimer = null;
          routeApplying = false;
  constructor(host) {
    this.host = host;
    this.ws = new StudioWsClient(() => {
      this.studioRevMismatch = true;
      this.host.requestUpdate();
    });
  }
  hostConnected() {
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }
  hostDisconnected() {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.fallbackPollTimer) {
      clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = null;
    }
    void this.flushAllPendingSettings();
    this.teardownSubscription();
  }
  hostUpdated() {
    if (this.pendingDomRevert) {
      const rev = this.pendingDomRevert;
      this.pendingDomRevert = null;
      const root = (this.host).renderRoot;
      if (root) {
        for (const [id, val] of Object.entries(rev.controlIds)) {
          const el = root.getElementById(id);
          if (!el) continue;
          if (typeof val === "boolean" && "checked" in el) {
            (el).checked = val;
          } else {
            el.value = String(val);
          }
        }
      }
    }
    if (this.pendingScrollCardId) {
      const cardId = this.pendingScrollCardId;
      this.pendingScrollCardId = "";
      const root = (this.host).renderRoot;
      const target = root?.getElementById(cardId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }
  setHass(hass) {
    const firstHass = !this.ws.hass && Boolean(hass);
    this.ws.setHass(hass);
    if (firstHass && this.host.isConnected) {
      void this.ensureSubscription(true);
    }
  }
  get hass() {
    return this.ws.hass;
  }
  reloadPage() {
    globalThis.location.reload();
  }
  showToast(message, isError = false) {
    this.toastMessage = String(message || "");
    this.toastIsError = isError;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastMessage = "";
      this.host.requestUpdate();
    }, isError ? 5000 : 3000);
    this.host.requestUpdate();
  }
  shouldIncludeLogs() {
    return this.currentScope === "system" && this.currentViewId === "system_tools" && this.logsOpen;
  }
  get pageTitle() {
    return VIEW_TITLES[this.currentViewId] || "All Devices";
  }
  get pageSubtitle() {
    if (this.currentScope === "device" && this.deviceSelected && this.state?.title) {
      return this.state.title;
    }
    return "";
  }
  // ---------- Routing & Navigation ----------
  applyRoute(route) {
    const rawPath = String(route?.path || "");
    const parts = rawPath
      .split("/")
      .filter(Boolean)
      .map((seg) => {
        try {
          return decodeURIComponent(seg);
        } catch {
          return seg;
        }
      });
    this.routeApplying = true;
    try {
      if (parts[0] === "devices" && parts[1]) {
        const nextSubId = parts[1];
        if (
          this.state &&
          Array.isArray(this.state.system_devices) &&
          !this.state.system_devices.some((d) => d.subentry_id === nextSubId)
        ) {
          this.redirectInvalidDeviceRoute();
          return;
        }
        const viewId = slugToView(DEVICE_VIEW_SLUGS, parts[2] || "overview") || "dashboard";
        const prevSubId = this.activeSubentryId;
        const subChanged = prevSubId !== nextSubId;
        if (prevSubId && subChanged) {
          void this.flushDeviceBucket(prevSubId);
        }
        this.activeSubentryId = nextSubId;
        this.deviceSelected = true;
        this.currentScope = "device";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (subChanged && this.ws.hass) {
          void this.ensureSubscription(true);
        }
      } else if (parts[0] === "system") {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        const viewId = slugToView(SYSTEM_VIEW_SLUGS, parts[1] || "overview") || "system_overview";
        this.currentScope = "system";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (this.ws.hass && this.shouldIncludeLogs()) {
          void this.refreshState({ includeLogs: true });
        }
      } else {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        this.deviceSelected = false;
        this.currentScope = "device";
        this.currentViewId = "select_device_prompt";
        this.host.requestUpdate();
      }
    } finally {
      this.routeApplying = false;
    }
  }
          redirectInvalidDeviceRoute() {
    const invalidId = this.activeSubentryId;
    this.activeSubentryId = "";
    this.deviceSelected = false;
    this.currentScope = "system";
    this.currentViewId = "system_overview";
    navigateHaPath("/latter/system/overview", true);
    if (invalidId) {
      this.showToast("Requested Device was not found; showing System Overview.", false);
    }
    this.host.requestUpdate();
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }
  syncUrl(replace = false) {
    if (this.routeApplying) return;
    let targetPath = "/latter";
    if (this.currentScope === "system") {
      const slug = SYSTEM_VIEW_SLUGS[this.currentViewId ] || "overview";
      targetPath = `/latter/system/${slug}`;
    } else if (this.deviceSelected && this.activeSubentryId && this.currentViewId !== "select_device_prompt") {
      const slug =
        DEVICE_VIEW_SLUGS[this.currentViewId ] ||
        "overview";
      targetPath = `/latter/devices/${encodeURIComponent(this.activeSubentryId)}/${slug}`;
    } else {
      targetPath = "/latter/devices";
    }
    if (globalThis.location?.pathname !== targetPath) {
      navigateHaPath(targetPath, replace);
    }
  }
  openDevicesLanding() {
    if (this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.deviceSelected = false;
    this.currentScope = "device";
    this.currentViewId = "select_device_prompt";
    this.syncUrl();
    this.host.requestUpdate();
  }
  openDevicesWithCategory(category) {
    this.deviceCategoryFilter = category;
    this.openDevicesLanding();
  }
  setScope(scope, explicitViewId) {
    if (scope === "device" && this.currentScope !== "device") {
      void this.flushSystemSettings();
    } else if (scope === "system" && this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.currentScope = scope;
    if (explicitViewId) {
      this.currentViewId = explicitViewId;
    } else if (scope === "system") {
      this.currentViewId = "system_overview";
    } else {
      this.currentViewId = this.deviceSelected && this.activeSubentryId ? "dashboard" : "select_device_prompt";
    }
    this.syncUrl();
    this.host.requestUpdate();
    if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }
  switchView(viewId) {
    if (viewId === "select_device_prompt") {
      this.openDevicesLanding();
      return;
    }
    const isSys = Object.prototype.hasOwnProperty.call(SYSTEM_VIEW_SLUGS, viewId);
    this.currentScope = isSys ? "system" : "device";
    this.currentViewId = viewId;
    this.syncUrl();
    this.host.requestUpdate();
    if (viewId === "area_tracking") {
      this.ensureDefaultSurveyDevice();
      void this.ensureSubscription(false);
    } else if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }
  openSystemSection(viewId, cardId = "") {
    this.pendingScrollCardId = cardId;
    this.switchView(viewId);
  }
  async switchSystemDevice(nextSubentryId, targetView = "dashboard") {
    const cleanNext = String(nextSubentryId || "").trim();
    if (!cleanNext) return;
    const prevSubId = this.activeSubentryId;
    if (prevSubId && prevSubId !== cleanNext) {
      await this.flushDeviceBucket(prevSubId);
    }
    this.activeSubentryId = cleanNext;
    this.deviceSelected = true;
    this.currentScope = "device";
    this.currentViewId = targetView === "select_device_prompt" ? "dashboard" : targetView;
    this.devicePinDraft = "";
    this.syncUrl();
    this.host.requestUpdate();
    await this.ensureSubscription(true);
  }
  openHaPage(path) {
    navigateHaPath(path, false);
  }
  openDeviceInHa() {
    const links = this.state?.links;
    const devId = links?.esphome_device_id || links?.latter_device_id || "";
    if (devId) {
      this.openHaPage(`/config/devices/device/${encodeURIComponent(devId)}`);
    } else {
      this.openHaPage("/config/integrations/integration/latter");
    }
  }
  toggleParentHaSidebar() {
    this.host.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }
  // ---------- Subscription & State Ingestion ----------
  teardownSubscription() {
    this.subGen += 1;
    if (typeof this.wsUnsub === "function") {
      try {
        this.wsUnsub();
      } catch {
        // Ignore stale unsubscribe errors on disconnect.
      }
    }
    this.wsUnsub = null;
    this.subscribedKey = "";
  }
          desiredSubscriptionKey() {
    const sub = this.activeSubentryId || "";
    const survey =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || ""
        : "";
    return `${sub}|${survey}`;
  }
  async ensureSubscription(forceRefresh = false) {
    if (!this.ws.hass?.connection) return;
    const nextKey = this.desiredSubscriptionKey();
    if (!forceRefresh && this.wsUnsub && this.subscribedKey === nextKey) {
      return;
    }
    this.teardownSubscription();
    const myGen = ++this.subGen;
    const targetSubId = this.activeSubentryId || null;
    const surveyId =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || null
        : null;
    if (forceRefresh || !this.state) {
      await this.refreshState({ includeLogs: this.shouldIncludeLogs() });
    }
    if (myGen !== this.subGen) return;
    try {
      const unsub = await this.ws.subscribe(
        {
          subentryId: targetSubId,
          surveySubentryId: surveyId,
          includeLogs: this.shouldIncludeLogs(),
        },
        (eventPayload) => {
          if (myGen !== this.subGen || !eventPayload) return;
          this.handleSubscriptionEvent(eventPayload);
        },
      );
      if (myGen !== this.subGen) {
        try {
          unsub();
        } catch {
          // Ignore stale teardown.
        }
        return;
      }
      this.wsUnsub = unsub;
      this.subscribedKey = nextKey;
    } catch {
      if (this.fallbackPollTimer) clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = setTimeout(() => {
        if (this.host.isConnected) {
          void this.ensureSubscription(true);
        }
      }, 10000);
    }
  }
  async refreshState(options) {
    if (!this.ws.hass) return;
    const targetSubId = this.activeSubentryId || null;
    const includeLogs = options?.includeLogs ?? this.shouldIncludeLogs();
    try {
      const payload = await this.ws.getState({
        subentryId: targetSubId,
        includeLogs,
      });
      if (payload) {
        this.loadError = "";
        this.loading = false;
        this.ingestPayload(payload, includeLogs);
      }
    } catch (err) {
      this.loading = false;
      this.loadError = formatWsError(err, "Latter Studio could not load.");
      this.host.requestUpdate();
    }
  }
          handleSubscriptionEvent(raw) {
    if (!raw || typeof raw !== "object") return;
    const rec = raw;
    const isBleDelta =
      rec.type === "ble_survey_delta" ||
      rec.event === "ble_survey_delta" ||
      (!("system_devices" in rec) &&
        ("ble_survey_rows" in rec || "ble_packets_seen" in rec || "area_presence_grid" in rec));
    if (isBleDelta) {
      this.applyBleSurveyDelta(rec);
      return;
    }
    const payload = raw;
    if (
      this.activeSubentryId &&
      payload.subentry_id &&
      payload.subentry_id !== this.activeSubentryId
    ) {
      return;
    }
    this.loading = false;
    this.loadError = "";
    this.ingestPayload(payload, false);
  }
          applyBleSurveyDelta(delta) {
    if (!this.state) return;
    const targetId = String(delta.subentry_id || this.bleSurveySubentryId || this.state.subentry_id || "");
    if (Array.isArray(delta.ble_survey_rows)) {
      const nextRows = delta.ble_survey_rows;
      const winRow = nextRows.find((r) => r.is_winner);
      if (Array.isArray(this.state.system_devices) && targetId) {
        this.state.system_devices = this.state.system_devices.map((dev) => {
          if (dev.subentry_id !== targetId) return dev;
          return {
            ...dev,
            ble_survey_rows: nextRows,
            ble_packets_seen:
              typeof delta.ble_packets_seen === "number" ? delta.ble_packets_seen : dev.ble_packets_seen,
            active_area_name: winRow?.area_name || dev.active_area_name,
          };
        });
      }
      if (this.state.subentry_id === targetId && this.state.live && typeof delta.ble_closest_proxy === "string") {
        this.state.live = {
          ...this.state.live,
          ble_closest_proxy: delta.ble_closest_proxy,
        };
      }
    }
    if (Array.isArray(delta.area_presence_grid) && this.state.live) {
      this.state.live = {
        ...this.state.live,
        area_presence_grid: delta.area_presence_grid,
      };
    }
    this.host.requestUpdate();
  }
  ingestPayload(incoming, logsWereRequested) {
    const prevCatalog = this.state?.catalog;
    const prevLogs = this.state?.internal_logs;
    if (
      this.deviceSelected &&
      this.activeSubentryId &&
      Array.isArray(incoming.system_devices) &&
      !incoming.system_devices.some((d) => d.subentry_id === this.activeSubentryId)
    ) {
      this.state = {
        ...incoming,
        catalog: incoming.catalog ?? prevCatalog,
        internal_logs: logsWereRequested || incoming.internal_logs?.length ? incoming.internal_logs : prevLogs || [],
      };
      this.redirectInvalidDeviceRoute();
      return;
    }
    const merged = {
      ...incoming,
      catalog: incoming.catalog ?? prevCatalog,
      internal_logs:
        logsWereRequested || (Array.isArray(incoming.internal_logs) && incoming.internal_logs.length > 0)
          ? incoming.internal_logs || []
          : prevLogs || [],
    };
    if (Object.keys(this.pendingSystemPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(this.pendingSystemPatch),
      };
    }
    const devBucket = merged.subentry_id ? this.pendingDeviceBuckets.get(merged.subentry_id) : undefined;
    if (devBucket && merged.config) {
      overlayDevicePrefsOnSections(merged, devBucket.patch);
    }
    overlayPendingEntityStates(merged, this.pendingEntityStates);
    if (this.currentScope === "device" && this.deviceSelected && merged.subentry_id === this.activeSubentryId) {
      const caps = merged.capabilities || {};
      const isBleTag = merged.config?.kind === "ble_tag";
      if (
        ((this.currentViewId === "display" || this.currentViewId === "interface") &&
          (isBleTag || !caps.has_display)) ||
        (this.currentViewId === "audio_voice" && (isBleTag || (!caps.has_audio && !caps.has_voice))) ||
        (this.currentViewId === "power" && (isBleTag || !caps.has_power))
      ) {
        this.currentViewId = "dashboard";
        this.syncUrl(true);
      }
    }
    this.state = merged;
    this.ensureDefaultSurveyDevice();
    this.ensureDefaultDoorbellTester();
    this.ensureDefaultSeedSelections();
    this.host.requestUpdate();
  }
          ensureDefaultSurveyDevice() {
    const devs = this.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.has_ble || d.ble_tracked || d.kind === "ble_tag");
    if (this.bleSurveySubentryId && bleDevs.some((d) => d.subentry_id === this.bleSurveySubentryId)) {
      return;
    }
    const current = bleDevs.find((d) => d.subentry_id === this.activeSubentryId);
    this.bleSurveySubentryId = current?.subentry_id || bleDevs[0]?.subentry_id || "";
  }
          ensureDefaultDoorbellTester() {
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (this.doorbellTestSubentryId && devs.some((d) => d.subentry_id === this.doorbellTestSubentryId)) {
      return;
    }
    this.doorbellTestSubentryId = devs[0]?.subentry_id || "";
  }
          ensureDefaultSeedSelections() {
    const groups = this.state?.device_groups || [];
    if (!this.seedGroupTargetId || !groups.some((g) => g.id === this.seedGroupTargetId)) {
      this.seedGroupTargetId = groups[0]?.id || "";
    }
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (!this.seedSourceSubentryId || !devs.some((d) => d.subentry_id === this.seedSourceSubentryId)) {
      this.seedSourceSubentryId = this.activeSubentryId || devs[0]?.subentry_id || "";
    }
  }
  // ---------- Delegated Domain Operations ----------
  stageDeviceSetting(key, value, controlDomId) {
    stageDeviceSettingOp(this, key, value, controlDomId);
  }
  async runDeviceAction(action, toastMessage) {
    return runDeviceActionOp(this, action, toastMessage);
  }
  async flushDeviceBucket(targetSubentryId) {
    await flushDeviceBucketOp(this, targetSubentryId);
  }
  stageSystemSetting(key, value, controlDomId) {
    stageSystemSettingOp(this, key, value, controlDomId);
  }
  async flushSystemSettings() {
    await flushSystemSettingsOp(this);
  }
  async flushAllPendingSettings() {
    const tasks = [];
    if (Object.keys(this.pendingSystemPatch).length > 0) {
      tasks.push(this.flushSystemSettings());
    }
    for (const subId of Array.from(this.pendingDeviceBuckets.keys())) {
      tasks.push(this.flushDeviceBucket(subId));
    }
    await Promise.allSettled(tasks);
  }
  getSectionItems(sectionId) {
    const sec = (this.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }
  async executeEntityAction(
    entityId,
    optimisticState,
    body,
    errorPrefix,
  ) {
    return executeEntityActionOp(this, entityId, optimisticState, body, errorPrefix);
  }
  async espAction(
    entityId,
    action,
    optimisticState,
    toastMessage,
  ) {
    const ok = await commitEntityChange(this, entityId, optimisticState, { action }, "Device action failed");
    if (ok && toastMessage) {
      this.showToast(toastMessage);
    }
    return ok;
  }
  async espSelect(entityId, option) {
    await commitEntityChange(this, entityId, option, { option }, "Could not update option");
  }
  async espNumber(entityId, level) {
    if (!Number.isFinite(level)) return;
    await commitEntityChange(this, entityId, String(level), { level }, "Could not update level");
  }
  async triggerHeaderFirmwareUpdate() {
    const updEntity = this.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    if (await this.espAction(updEntity, "install")) {
      this.showToast("Firmware update started");
    }
  }
  getEnabledDockTokens() {
    return getEnabledDockTokensOp(this);
  }
  toggleDockAppToken(appId) {
    toggleDockAppTokenOp(this, appId);
  }
  moveDockAppToken(appId, delta) {
    moveDockAppTokenOp(this, appId, delta);
  }
  getEnabledAreaCategories() {
    return getEnabledAreaCategoriesOp(this);
  }
  toggleAreaCategoryToken(token) {
    toggleAreaCategoryTokenOp(this, token);
  }
  moveAreaCategoryToken(token, delta) {
    moveAreaCategoryTokenOp(this, token, delta);
  }
  getEnabledActivitySources() {
    return getEnabledActivitySourcesOp(this);
  }
  toggleActivitySource(sourceId) {
    toggleActivitySourceOp(this, sourceId);
  }
  applyDeviceCustomColor(hex, switchColorProfile = true) {
    applyDeviceCustomColorOp(this, hex, switchColorProfile);
  }
  openColorWheelModal(targetScope) {
    openColorWheelModalOp(this, targetScope);
  }
  closeColorWheelModal() {
    this.colorWheelModal = { ...this.colorWheelModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async saveColorWheelSelection() {
    await saveColorWheelSelectionOp(this);
  }
  deleteCustomPalette(hex) {
    deleteCustomPaletteOp(this, hex);
  }
  async uploadWallpaper(scope) {
    await uploadWallpaperOp(this, scope);
  }
  async selectWallpaperSource(sourceId) {
    await selectWallpaperSourceOp(this, sourceId);
  }
  async setWallpaperRotation(minutes) {
    await setWallpaperRotationOp(this, minutes);
  }
  async toggleWallpaperFav(sourceId) {
    await toggleWallpaperFavOp(this, sourceId);
  }
  async setAllWallpaperFavorites(sourceIds) {
    await setAllWallpaperFavoritesOp(this, sourceIds);
  }
  async deleteWallpaper(scope, sourceId) {
    await deleteWallpaperOp(this, scope, sourceId);
  }
  get hasConfiguredSecurityPin() {
    return Boolean(
      this.state?.config?.has_security_pin ??
        this.state?.live?.has_security_pin ??
        this.state?.has_security_pin,
    );
  }
  async saveSecurityPin(fromScope) {
    await saveSecurityPinOp(this, fromScope);
  }
  async clearSecurityPin(fromScope) {
    await clearSecurityPinOp(this, fromScope);
  }
  async rotateSigningKey() {
    await rotateSigningKeyOp(this);
  }
  async downloadDeviceDiagnostics() {
    await downloadDeviceDiagnosticsOp(this);
  }
  openRemoveDeviceModal(subentryId, title) {
    if (!subentryId) return;
    this.removeModal = { open: true, subentryId, title: title || "Device", busy: false };
    this.host.requestUpdate();
  }
  closeRemoveDeviceModal() {
    this.removeModal = { ...this.removeModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async confirmRemoveDevice() {
    await confirmRemoveDeviceOp(this);
  }
  openResetDeviceModal() {
    if (!this.activeSubentryId) return;
    const isBleTag = this.state?.config?.kind === "ble_tag";
    this.resetModal = {
      open: true,
      deviceSettings: !isBleTag,
      latterOptions: true,
      busy: false,
    };
    this.host.requestUpdate();
  }
  closeResetDeviceModal() {
    this.resetModal = { ...this.resetModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async confirmResetDevice() {
    await confirmResetDeviceOp(this);
  }
  openAddBleModal(prefill) {
    this.addBleModal = {
      open: true,
      candidateAddr: prefill?.address || "",
      name: prefill?.name || "",
      address: prefill?.address || "",
      assignedPerson: "",
      busy: false,
    };
    this.host.requestUpdate();
  }
  closeAddBleModal() {
    this.addBleModal = { ...this.addBleModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  selectBleCandidateInModal(addr) {
    selectBleCandidateInModalOp(this, addr);
  }
  async quickAdoptBleCandidate(title, targetAddress, assignedPerson = "") {
    await quickAdoptBleCandidateOp(this, title, targetAddress, assignedPerson);
  }
  async confirmAddBleModal() {
    await confirmAddBleModalOp(this);
  }
  async checkSystemUpdates() {
    await checkSystemUpdatesOp(this);
  }
  updateStringListRow(
    key,
    index,
    value,
  ) {
    updateStringListRowOp(this, key, index, value);
  }
  addStringListRow(
    key,
    defaultEntity = "",
    maxLen = 10,
  ) {
    addStringListRowOp(this, key, defaultEntity, maxLen);
  }
  removeStringListRow(key, index) {
    removeStringListRowOp(this, key, index);
  }
  addVolumeOverrideRow() {
    addVolumeOverrideRowOp(this);
  }
  updateVolumeOverrideRow(index, field, value) {
    updateVolumeOverrideRowOp(this, index, field, value);
  }
  removeVolumeOverrideRow(index) {
    removeVolumeOverrideRowOp(this, index);
  }
  addRemoteGroupRow() {
    addRemoteGroupRowOp(this);
  }
  updateRemoteGroupField(groupId, field, value) {
    updateRemoteGroupFieldOp(this, groupId, field, value);
  }
  toggleRemoteInGroup(groupId, remoteEntity) {
    toggleRemoteInGroupOp(this, groupId, remoteEntity);
  }
  removeRemoteGroupRow(groupId) {
    removeRemoteGroupRowOp(this, groupId);
  }
  async previewCamera(cameraEntity, bustCache = false) {
    await previewCameraOp(this, cameraEntity, bustCache);
  }
  closeCameraPreview() {
    this.activeCameraPreviewEntity = "";
    this.cameraPreviewUrl = "";
    this.host.requestUpdate();
  }
  async testDoorbellSpeaker() {
    await testDoorbellSpeakerOp(this);
  }
  async createDeviceGroup() {
    await createDeviceGroupOp(this);
  }
  async deleteDeviceGroup(groupId) {
    await deleteDeviceGroupOp(this, groupId);
  }
  async syncDeviceGroup(groupId, singleSubentryId) {
    await syncDeviceGroupOp(this, groupId, singleSubentryId);
  }
  async seedGroupBaselineFromDevice() {
    await seedGroupBaselineFromDeviceOp(this);
  }
  resolvedGroupCtrlId() {
    return resolvedGroupCtrlIdOp(this);
  }
  async setGroupDeviceSetting(patch) {
    await setGroupDeviceSettingOp(this, patch);
  }
  filteredControlTargets(ctrl) {
    return filteredControlTargetsOp(this, ctrl);
  }
  async bulkToggle(ctrl, turnOn) {
    await bulkToggleOp(this, ctrl, turnOn);
  }
  async bulkSelect(ctrl, option) {
    await bulkSelectOp(this, ctrl, option);
  }
  async bulkNumber(ctrl, level) {
    await bulkNumberOp(this, ctrl, level);
  }
  selectBleSurveyDevice(subentryId) {
    this.bleSurveySubentryId = subentryId;
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }
  toggleBleLiveStream(enabled) {
    this.bleLiveStreamActive = enabled;
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }
  getActiveSurveyDevice() {
    return getActiveSurveyDeviceOp(this);
  }
  async setBleOffset(areaId, offsetDb) {
    await setBleOffsetOp(this, areaId, offsetDb);
  }
  async autoCalibrateHere(areaId) {
    await autoCalibrateHereOp(this, areaId);
  }
  async setAreaFusion(
    areaId,
    update,
  ) {
    await setAreaFusionOp(this, areaId, update);
  }
  async sendAnnouncement() {
    await sendAnnouncementOp(this);
  }
  async exportBackup(explicitSubentryId) {
    await exportBackupOp(this, explicitSubentryId);
  }
  async restoreFromUploadedFile() {
    await restoreFromUploadedFileOp(this);
  }
  onToggleLogsDetails(open) {
    this.logsOpen = open;
    this.host.requestUpdate();
    if (open) {
      void this.refreshState({ includeLogs: true });
    }
  }
  formatVisibleLogs() {
    return formatVisibleLogsOp(this);
  }
  async copyLogsToClipboard() {
    await copyLogsToClipboardOp(this);
  }
  async clearInternalLogs() {
    await clearInternalLogsOp(this);
  }
}

// --- src/styles/tokens.ts ---
/**
 * Latter Studio Design System Tokens & Stylesheet (`docs/studio-design.md` §3).
 * Literal font sizes, pixel spacing, and colors appear ONLY inside the single `:host` block.
 */
const STUDIO_STYLES = css`
  :host {
    /* Design tokens (docs/studio-design.md section 3). Every visual value reads a token; each token
       reads a Home Assistant theme variable, with a fallback for themes that do not set it. */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.6);
    --studio-line-height-condensed: var(--ha-line-height-condensed, 1.2);
    --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
    --studio-card-title-tracking: -0.012em;
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-card-top: var(--ha-space-5, 20px);
    --studio-space-5: var(--ha-space-6, 24px);
    --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-field: var(--ha-border-radius-sm, 4px);
    --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
    --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-card-border-width: var(--ha-card-border-width, 1px);
    --studio-control-height: var(--ha-button-height, 40px);
    --studio-control-height-compact: 32px;
    --studio-row-min-height: 56px;
    --studio-header-height: var(--header-height, 56px);
    --studio-sidebar-width: 244px;
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #282828);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #9b9b9b));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, rgba(255, 255, 255, 0.05));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #363636));
    --studio-field-bg-hover: var(--ha-color-form-background-hover, var(--studio-field-bg));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(255, 255, 255, 0.42)));
    --studio-popup-bg: var(--card-background-color, #1c1c1c);
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #9b9b9b);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #009ac7);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 0, 154, 199), 0.12);
    --studio-primary-tint-strong: rgba(var(--rgb-primary-color, 0, 154, 199), 0.24);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);
    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, var(--primary-color, #009ac7));
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, var(--studio-btn-accent-bg));
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, var(--text-primary-color, #ffffff));
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint));
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, var(--studio-primary-tint-strong));
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, var(--primary-color, #009ac7));
    --studio-btn-plain-hover: var(--ha-color-fill-primary-quiet-resting, var(--studio-primary-tint));
    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, var(--studio-error-tint));
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, var(--error-color, #db4437));
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, var(--error-color, #db4437));
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);
    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #202020));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #989898));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint-strong)));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, var(--primary-color, #009ac7)));
    --studio-switch-thumb-shadow: var(--ha-switch-thumb-box-shadow, var(--ha-box-shadow-s, 0 1px 2px rgba(0, 0, 0, 0.3)));
    --studio-toast-bg: var(--primary-text-color, #e1e1e1);
    --studio-toast-text: var(--card-background-color, #1c1c1c);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(110, 110, 110));
    --studio-success: var(--success-color, #43a047);
    --studio-warning: var(--warning-color, #ffa600);
    --studio-error: var(--error-color, #db4437);
    --studio-info: var(--info-color, #039be5);
    --studio-success-tint: color-mix(in srgb, var(--studio-success) 14%, transparent);
    --studio-warning-tint: color-mix(in srgb, var(--studio-warning) 14%, transparent);
    --studio-error-tint: color-mix(in srgb, var(--studio-error) 14%, transparent);
    --studio-info-tint: color-mix(in srgb, var(--studio-info) 14%, transparent);
    --studio-card-shadow: var(--ha-card-box-shadow, none);
    --studio-overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --studio-scrim: rgba(0, 0, 0, 0.5);
    --studio-media-bg: var(--secondary-background-color, #000000);
    display: block;
    min-height: 100vh;
    background: var(--studio-bg);
    color: var(--studio-text);
    font-family: var(--studio-font-family);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
    color-scheme: light;
    scrollbar-color: var(--studio-scrollbar-thumb) transparent;
    scrollbar-width: thin;
  }
  :host([dark]) { color-scheme: dark; }
  * { box-sizing: border-box; }
  .hidden { display: none !important; }
  .studio-root {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--studio-bg);
  }
  h2, h3, h4, p { margin: 0; }
  code, .mono {
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* ---------- Upgrade banner ---------- */
  .studio-rev-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    background: var(--studio-warning-tint);
    border-bottom: 1px solid var(--studio-warning);
    color: var(--studio-text);
    z-index: 40;
  }

  /* ---------- Title bar ---------- */
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding: 0 var(--studio-space-3);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-bottom: var(--studio-header-border);
    position: sticky;
    top: 0;
    z-index: 30;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
    user-select: none;
  }
  .titlebar-brand .ha-menu-btn { color: var(--studio-header-icon); display: none; }
  :host([narrow]) .titlebar-brand .ha-menu-btn { display: inline-flex; }
  .titlebar-title { padding-inline-start: var(--studio-space-3); }
  :host([narrow]) .titlebar-title { padding-inline-start: 0; }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }

  /* ---------- Shell & navigation ---------- */
  .app-shell {
    display: grid;
    grid-template-columns: var(--studio-sidebar-width) minmax(0, 1fr);
    min-height: calc(100vh - var(--studio-header-height));
  }
  aside.sidebar {
    background: var(--studio-sidebar-bg);
    border-right: 1px solid var(--studio-divider);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-4) var(--studio-space-3);
    position: sticky;
    top: var(--studio-header-height);
    height: calc(100vh - var(--studio-header-height));
    overflow-y: auto;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    background: var(--studio-input-bg);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .scope-tab {
    min-height: var(--studio-control-height-compact);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .scope-tab.active {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    width: 100%;
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
  }
  .nav-btn:hover { background: var(--studio-hover); }
  .nav-btn.active {
    background: var(--studio-primary-tint);
    color: var(--studio-primary);
  }
  .nav-btn.nav-back-btn { color: var(--studio-text-secondary); }
  .nav-device-title {
    padding: var(--studio-space-2) var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    border-bottom: 1px solid var(--studio-divider);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-4); }
  .nav-badge {
    min-width: 20px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .main-area { min-width: 0; }
  .content-wrap {
    max-width: 1140px;
    margin: 0 auto;
    padding: var(--studio-space-5) var(--studio-space-5) var(--studio-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    container-type: inline-size;
    container-name: studio-content;
  }
  .content-wrap > section {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
  }
  .page-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
  }
  .page-subtitle {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .is-loading .content-wrap > section { display: none !important; }
  .columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-4);
    align-items: start;
  }
  .column {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    min-width: 0;
  }
  @container studio-content (max-width: 760px) {
    .columns { grid-template-columns: minmax(0, 1fr); }
  }

  /* ---------- Card ---------- */
  .card {
    min-width: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: var(--studio-card-border-width) solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
    color: var(--studio-text);
  }
  .card.danger { border-color: var(--studio-error); }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-card-top) var(--studio-space-4) 0;
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    min-width: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    letter-spacing: var(--studio-card-title-tracking);
    line-height: var(--studio-line-height-condensed);
  }
  .card-subtitle, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .card-header-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .card-content {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-4);
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-bottom: var(--studio-space-card-top);
  }
  details.card > summary::-webkit-details-marker { display: none; }
  details.card > summary::after {
    content: "▾";
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.card[open] > summary::after { transform: rotate(180deg); }
  details.card[open] > summary { border-bottom: 1px solid var(--studio-divider); }
  details.sub-collapsible {
    border-top: 1px solid var(--studio-divider);
    padding-top: var(--studio-space-3);
  }
  details.sub-collapsible > summary {
    cursor: pointer;
    font-weight: var(--studio-weight-medium);
  }
  details.sub-collapsible > .card-content { padding: var(--studio-space-3) 0 0; }
  .fusion-area { border-bottom: 1px solid var(--studio-divider); padding-bottom: var(--studio-space-3); }
  .fusion-area:last-child { border-bottom: none; }
  .fusion-area > .settings-row { border-bottom: none; }
  .subsection-title {
    padding-top: var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }
  .card-content > .subsection-title:first-child { padding-top: 0; border-top: none; }

  /* ---------- Settings row & controls ---------- */
  .settings-list {
    display: flex;
    flex-direction: column;
  }
  .settings-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--studio-space-4);
    min-height: var(--studio-row-min-height);
    padding: var(--studio-space-2) 0;
  }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .row-label { font-weight: var(--studio-weight-regular); }
  .row-description { line-height: normal; }
  .settings-row-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .settings-row-control select,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="search"],
  .settings-row-control input[type="number"],
  .settings-row-control input[type="password"] {
    width: 260px;
    max-width: 100%;
  }
  .settings-row-control input[type="number"],
  .settings-row-control input[type="password"] { width: 140px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; width: auto; }
  select, input[type="text"], input[type="search"], input[type="number"], input[type="password"], textarea {
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-bottom: 1px solid var(--studio-field-line);
    border-radius: var(--studio-radius-field) var(--studio-radius-field) 0 0;
    background: var(--studio-field-bg);
    color: var(--studio-text);
    font: inherit;
    transition: background-color 0.15s ease-out;
  }
  textarea {
    padding: var(--studio-space-2) var(--studio-space-3);
    resize: vertical;
  }
  select:hover, input[type="text"]:hover, input[type="search"]:hover, input[type="number"]:hover, input[type="password"]:hover, textarea:hover { background: var(--studio-field-bg-hover); }
  select option, select optgroup { background-color: var(--studio-popup-bg); color: var(--studio-text); }
  input::placeholder, textarea::placeholder { color: var(--studio-text-secondary); opacity: 1; }
  input[readonly] { color: var(--studio-text-secondary); }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { width: 140px; accent-color: var(--studio-primary); }
  select:focus-visible, input:focus-visible, textarea:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  select:focus-visible, input[type="text"]:focus-visible, input[type="search"]:focus-visible, input[type="number"]:focus-visible, input[type="password"]:focus-visible, textarea:focus-visible {
    outline: none;
    border-bottom-color: var(--studio-primary);
    box-shadow: inset 0 -1px 0 var(--studio-primary);
  }
  .switch {
    appearance: none;
    position: relative;
    width: 48px;
    height: 24px;
    margin: 0;
    border: 1px solid var(--studio-switch-border);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-switch-track);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--studio-switch-thumb);
    box-shadow: var(--studio-switch-thumb-shadow);
    transition: transform 0.15s ease, background-color 0.15s ease;
  }
  .switch:checked { background: var(--studio-switch-on-track); border-color: var(--studio-switch-on-border); }
  .switch:checked::after { transform: translateX(24px); background: var(--studio-switch-on-thumb); }
  .switch:disabled { opacity: 0.3; cursor: not-allowed; }
  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input:not([type="file"]), .input-action-row > select { flex: 1 1 180px; min-width: 0; }
  .input-action-row > input[type="file"] { flex: 0 1 auto; max-width: 100%; }
  .segmented {
    display: inline-flex;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
  }
  .segmented button {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .segmented button[aria-checked="true"] { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .inline-switch { display: inline-flex; align-items: center; gap: var(--studio-space-2); cursor: pointer; white-space: nowrap; }
  .list-row {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-main {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--studio-space-2);
    flex: 1;
    min-width: 0;
  }
  .list-row-grow { flex: 1; min-width: 0; }
  .list-block {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-head {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
  }
  .stacked-field {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .stacked-field > label, .stacked-field > .field-label {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .stacked-field > select, .stacked-field > input { width: 100%; }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }

  /* ---------- Buttons ---------- */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-4);
    border: none;
    border-radius: var(--studio-radius-button);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease-out;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-btn-accent-bg); color: var(--studio-btn-accent-text); }
  .btn-primary:hover:not(:disabled) { background: var(--studio-btn-accent-bg-hover); }
  .btn-secondary { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .btn-secondary:hover:not(:disabled) { background: var(--studio-btn-tonal-bg-hover); }
  .btn-text {
    background: transparent;
    color: var(--studio-btn-tonal-text);
    padding: 0 var(--studio-space-3);
  }
  .btn-text:hover:not(:disabled) { background: var(--studio-btn-plain-hover); }
  .btn-danger { background: var(--studio-danger-tonal-bg); color: var(--studio-danger-tonal-text); }
  .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
  .btn-danger-filled { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .btn-icon:hover { background: var(--studio-hover); }
  .btn-icon.danger { color: var(--studio-error); }
  .btn-icon svg { width: 20px; height: 20px; fill: currentColor; }
  .quick-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
    padding-bottom: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
  }
  .quick-action-grid:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
  .quick-action-btn {
    justify-content: flex-start;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-2) var(--studio-space-3);
    border-radius: var(--studio-radius-control);
    white-space: normal;
    text-align: left;
    line-height: var(--studio-line-height-condensed);
  }
  .quick-action-btn svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
    flex-shrink: 0;
  }

  /* ---------- Data display ---------- */
  .kv-list { display: flex; flex-direction: column; gap: 0; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-1) 0;
  }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  button.kv-row {
    width: 100%;
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  button.kv-row:hover { background: var(--studio-hover); }
  button.kv-row > strong::after {
    content: " ›";
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  table.data-table th {
    padding: 0;
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  .sort-btn {
    width: 100%;
    padding: var(--studio-space-3) var(--studio-space-3);
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: left;
    cursor: pointer;
  }
  .sort-btn:hover { color: var(--studio-text); }
  th[aria-sort="ascending"] .sort-btn, th[aria-sort="descending"] .sort-btn { color: var(--studio-primary); }
  table.data-table td {
    padding: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  table.data-table tbody tr:last-child td { border-bottom: none; }
  table.data-table tbody tr { cursor: pointer; }
  table.data-table tbody tr:hover, table.data-table tbody tr:focus-visible { background: var(--studio-hover); }
  td.col-name { font-weight: var(--studio-weight-medium); }
  td.col-open { color: var(--studio-text-secondary); text-align: right; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: 22px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .chip-primary { background: var(--studio-primary-tint); color: var(--studio-primary); }
  .chip-success { background: var(--studio-success-tint); color: var(--studio-success); }
  .chip-warning { background: var(--studio-warning-tint); color: var(--studio-warning); }
  .chip-error { background: var(--studio-error-tint); color: var(--studio-error); }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    margin-right: var(--studio-space-2);
    border-radius: 50%;
    background: var(--studio-text-disabled);
  }
  .chip > .status-dot { margin-right: var(--studio-space-1); }
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }
  .status-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
  }
  @media (max-width: 480px) {
    .status-tiles { grid-template-columns: minmax(0, 1fr); }
  }
  .status-tile {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-1);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: left;
  }
  button.status-tile {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.status-tile:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  button.status-tile:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .status-tile-head {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile-head svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .status-tile-value {
    margin-top: var(--studio-space-1);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .status-tile-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile > .signal-track { margin-top: var(--studio-space-1); }
  .status-assignments {
    padding-top: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  .status-assignments strong {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--studio-space-2);
  }
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .pill.enabled {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    color: var(--studio-text);
  }
  .pill-move {
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    padding: 0 var(--studio-space-1);
    cursor: pointer;
  }
  .pill-move:hover { color: var(--studio-primary); }
  .pill-toggle {
    padding: 0;
    border: none;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .swatch {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* ---------- BLE rows & upload progress ---------- */
  .signal-row {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .signal-row.winner { border-color: var(--studio-primary); }
  .signal-row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-row-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-meta { color: var(--studio-text-secondary); font-size:var(--studio-font-secondary); }
  .signal-track, .upload-progress {
    height: 6px;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface-alt);
    overflow: hidden;
  }
  .signal-fill {
    width: var(--signal-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.25s ease;
  }
  .signal-fill.low { background: var(--studio-error); }
  .upload-progress-fill {
    width: var(--upload-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.15s ease;
  }

  /* ---------- Wallpapers ---------- */
  .wp-upload-trigger {
    display: inline-flex;
    align-items: center;
  }
  .wp-upload-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
  }
  .wp-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--studio-space-3);
  }
  .wp-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    text-align: center;
  }
  .wp-gallery > .empty-state { grid-column: 1 / -1; }
  .wp-card.active { border-color: var(--studio-primary); background: var(--studio-primary-tint); }
  .wp-thumb-btn {
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--studio-radius-control);
    cursor: pointer;
    line-height: 0;
  }
  .wp-thumb-btn.circle { border-radius: 50%; }
  .wp-thumb-btn:hover .wp-thumb { border-color: var(--studio-primary); }
  .wp-thumb-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .wp-thumb {
    width: 104px;
    height: 104px;
    object-fit: cover;
    background: var(--studio-media-bg);
    border: 1px solid var(--studio-divider);
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: var(--studio-radius-control); }
  .wp-title {
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    overflow-wrap: anywhere;
  }
  .wp-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    margin-top: auto;
    width: 100%;
  }
  .btn-icon.wp-star-btn {
    width: var(--studio-control-height-compact);
    height: var(--studio-control-height-compact);
  }
  .btn-icon.wp-star-btn:hover {
    color: var(--studio-warning);
    background: var(--studio-warning-tint);
  }
  .btn-icon.wp-star-btn.starred {
    color: var(--studio-warning);
  }
  .cam-preview {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .cam-preview img {
    width: 100%;
    max-width: 360px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
  }
  .log-output {
    max-height: 380px;
    margin: 0;
    padding: var(--studio-space-3);
    overflow: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    white-space: pre-wrap;
  }

  /* ---------- States ---------- */
  .empty-state {
    padding: var(--studio-space-3) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-5) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state::before {
    content: "";
    width: 20px;
    height: 20px;
    border: 2px solid var(--studio-divider);
    border-top-color: var(--studio-primary);
    border-radius: 50%;
    animation: studio-spin 0.8s linear infinite;
  }
  .studio-root:not(.is-loading) #studio-loading { display: none; }
  @keyframes studio-spin { to { transform: rotate(360deg); } }
  .alert {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-info-tint);
  }
  .alert-error { background: var(--studio-error-tint); }
  .alert-warning { background: var(--studio-warning-tint); }
  .alert-body { display: flex; flex-direction: column; gap: var(--studio-space-1); min-width: 0; }
  .alert-list { margin: 0; padding-left: var(--studio-space-5); }
  .toast {
    position: fixed;
    left: 50%;
    bottom: var(--studio-space-5);
    transform: translateX(-50%);
    z-index: 50;
    max-width: min(560px, calc(100vw - 32px));
    padding: var(--studio-space-3) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-toast-bg);
    color: var(--studio-toast-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  .toast.error { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .offscreen { position: fixed; top: -9999px; left: -9999px; }

  /* ---------- Dialogs ---------- */
  dialog.studio-dialog {
    width: min(460px, calc(100vw - 32px));
    padding: var(--studio-space-5);
    border: none;
    border-radius: var(--studio-radius-dialog);
    background: var(--studio-surface);
    color: var(--studio-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  dialog.studio-dialog::backdrop { background: var(--studio-scrim); }
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .dialog-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height-condensed);
  }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--studio-space-2);
    margin-top: var(--studio-space-2);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input[type="text"] { width: 120px; font-family: var(--studio-font-code); text-align: center; }
  .color-hex-row input[type="color"] {
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: none;
    cursor: pointer;
  }

  /* ---------- Narrow cards and screens ---------- */
  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @container (max-width: 360px) {
    .quick-action-grid { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .titlebar-title { padding-inline-start: 0; }
    .app-shell { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
    aside.sidebar {
      align-self: start;
      position: sticky;
      top: var(--studio-header-height);
      z-index: 25;
      height: auto;
      padding: var(--studio-space-2) var(--studio-space-3);
      border-right: none;
      border-bottom: 1px solid var(--studio-divider);
    }
    .nav-device-title { display: none; }
    .nav-list { flex-direction: row; overflow-x: auto; scrollbar-width: none; }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn { width: auto; border: 1px solid var(--studio-divider); border-radius: var(--studio-radius-pill); }
    #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-3); }
    .content-wrap { padding: var(--studio-space-4) var(--studio-space-3) var(--studio-space-5); }
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @media (max-width: 480px) {
    .list-row { flex-wrap: wrap; }
    .list-row-head { flex-wrap: wrap; }
    .list-row-main { grid-template-columns: minmax(0, 1fr); width: 100%; }
  }
`;

// --- src/components/wallpaper-gallery.ts ---
/**
 * Wallpaper Gallery & Multipart XHR Upload Component (Device & System scopes).
 */
function renderStarIcon(filled) {
  if (filled) {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.45 4.73L5.82 21 12 17.27Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M12 15.39l-3.76 2.27.99-4.28-3.32-2.88 4.38-.38L12 6.09l1.71 4.03 4.38.38-3.32 2.88.99 4.28L12 15.39M22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.45 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24Z"
    />
  </svg>`;
}
function renderWallpaperGalleryItems(
  store,
  scope,
  items,
  displayShape,
) {
  if (!items.length) {
    return html`<p class="empty-state">No wallpapers available yet.</p>`;
  }
  const shapeClass = displayShape === "circle" ? "circle" : "square";
  return html`${repeat(
    items,
    (wp) => wp.id,
    (wp) => {
      const label = wp.name || wp.id;
      const isActive = Boolean(wp.active);
      const isFav = Boolean(wp.favorite);
      const canDelete = Boolean(wp.deletable ?? wp.kind === "upload");
      const thumbSrc = wp.thumb_url || wp.preview_url || "";
      const activeCls = isActive ? "wp-card active" : "wp-card";
      const onUse = () => {
        void store.selectWallpaperSource(wp.id);
      };
      const onFav = () => {
        void store.toggleWallpaperFav(wp.id);
      };
      const onDel = () => {
        void store.deleteWallpaper(scope, wp.id);
      };
      const thumbImg = thumbSrc
        ? html`<img src=${thumbSrc} alt=${label} loading="lazy" class="wp-thumb ${shapeClass}" />`
        : html`<div class="wp-thumb ${shapeClass}"></div>`;
      return html`<div class=${activeCls}>
        ${scope === "device" && !isActive
          ? html`<button
              type="button"
              aria-label=${`Use wallpaper ${label}`}
              @click=${onUse}
              class="wp-thumb-btn ${shapeClass}"
            >
              ${thumbImg}
            </button>`
          : thumbImg}
        <div class="wp-title">${label}</div>
        <div class="wp-actions">
          ${scope === "device"
            ? html`${isActive
                  ? html`<span class="chip chip-primary">Active</span>`
                  : html`<button type="button" @click=${onUse} class="btn btn-secondary btn-compact">
                      Use
                    </button>`}
                <button
                  type="button"
                  aria-label=${isFav ? `Remove ${label} from favorites` : `Star ${label} for rotation`}
                  aria-pressed=${String(isFav)}
                  title=${isFav ? "Starred for rotation" : "Star for rotation"}
                  @click=${onFav}
                  class="btn-icon wp-star-btn${isFav ? " starred" : ""}"
                >
                  ${renderStarIcon(isFav)}
                </button>
                ${canDelete ? renderTrashIconButton(`Delete wallpaper ${label}`, onDel) : nothing}`
            : canDelete
              ? html`<span class="chip chip-primary">Uploaded</span>
                  ${renderTrashIconButton(`Delete wallpaper ${label}`, onDel)}`
              : html`<span class="chip">Built-in</span>`}
        </div>
      </div>`;
    },
  )}`;
}
function renderWallpaperUploadTrigger(
  store,
  scope,
) {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
  const btnId = scope === "device" ? "btn-upload-wp" : "btn-upload-sys-wp";
  const onFilePick = (ev) => {
    const input = ev.currentTarget;
    const f = input.files && input.files[0] ? input.files[0] : null;
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = f;
    } else {
      store.selectedSystemWallpaperFile = f;
    }
    if (f) {
      void store.uploadWallpaper(scope);
    } else {
      store.host.requestUpdate();
    }
  };
  const onTriggerPick = (ev) => {
    const btn = ev.currentTarget;
    const fileInput = btn?.parentElement?.querySelector("input[type='file']")
            ;
    fileInput?.click();
  };
  return html`<span class="wp-upload-trigger">
    <input
      type="file"
      id=${inputId}
      accept="image/*"
      aria-label="Wallpaper image (up to 15 MB)"
      @change=${onFilePick}
      class="offscreen"
    />
    <button
      type="button"
      id=${btnId}
      ?disabled=${store.uploadBusy}
      @click=${onTriggerPick}
      class="btn btn-secondary btn-compact"
    >
      ${isUploadingThisScope ? "Uploading…" : "Upload Photo"}
    </button>
  </span>`;
}
function renderWallpaperUploadProgress(
  store,
  scope,
) {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  if (!isUploadingThisScope) return nothing;
  const pctStyle = `--upload-pct:${store.uploadPercent}%`;
  return html`<div class="stack">
    <div class="wp-upload-status">
      <span>Uploading photo…</span>
      <span class="chip chip-primary">${store.uploadPercent}%</span>
    </div>
    <div
      class="upload-progress"
      role="progressbar"
      aria-valuenow=${String(store.uploadPercent)}
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="upload-progress-fill" style=${pctStyle}></div>
    </div>
  </div>`;
}

// --- src/views/device-display-view.ts ---
/**
 * Device Display View (`display`, D-027 / D-029 / D-033 / D-034):
 * Visual & aesthetic preferences across screens.
 * Column 1: Home Screen (Wake Greeting, Weather Background & Sun & Moon), Screensavers, Voice Assistant (Visual Profile), Brightness & Clock.
 * Column 2: Colors, Wallpapers & Media Player (Album Art & Overlay Style).
 */
function sortEntitiesByKeywords(
  items,
  order,
) {
  return [...items].sort((a, b) => {
    const la = (a.name || "").toLowerCase();
    const lb = (b.name || "").toLowerCase();
    const ia = order.findIndex((k) => la.includes(k));
    const ib = order.findIndex((k) => lb.includes(k));
    const ra = ia >= 0 ? ia : order.length;
    const rb = ib >= 0 ? ib : order.length;
    return ra - rb;
  });
}
function isInterfaceDisplayEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return low.includes("start screen") || low.includes("start_screen");
}
function isClockDisplayEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("clock face") ||
    low.includes("clock_face") ||
    low.includes("time format") ||
    low.includes("time_format")
  );
}
function isMediaAppearanceEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("album art style") ||
    low.includes("album_art_style") ||
    low.includes("overlay style") ||
    low.includes("music_overlay_style")
  );
}
function isScreensaverSleepEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("screensaver") ||
    low.includes("docked idle timeout") ||
    low.includes("docked_idle_timeout")
  );
}
function isVoiceVisualProfileEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return low.includes("visual profile") || low.includes("visual_profile");
}
function isColorDisplayEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return low.includes("color profile") || low.includes("color_profile");
}
function renderDeviceDisplayView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = data?.system_config?.custom_palettes || [];
  const brightnessOrder = [
    "auto brightness mode",
    "manual brightness",
    "day brightness",
    "night brightness",
    "day start hour",
    "night start hour",
  ];
  const allDisplayItems = store
    .getSectionItems("display")
    .filter((it) => !isInterfaceDisplayEntity(it));
  const colorItems = allDisplayItems.filter(isColorDisplayEntity);
  const clockItems = sortEntitiesByKeywords(
    allDisplayItems.filter(isClockDisplayEntity),
    ["clock face", "time format"],
  );
  const brightnessItems = sortEntitiesByKeywords(
    allDisplayItems.filter((it) => !isColorDisplayEntity(it) && !isClockDisplayEntity(it)),
    brightnessOrder,
  );
  const autoBrtItem = brightnessItems.find((it) =>
    (it.name || "").toLowerCase().includes("auto brightness"),
  );
  const autoBrtState = String(autoBrtItem?.state ?? "").trim();
  const autoBrtKnown =
    Boolean(autoBrtItem) &&
    autoBrtState !== "" &&
    autoBrtState !== "unavailable" &&
    autoBrtState !== "unknown";
  const autoBrtOff = autoBrtKnown && (autoBrtState === "Disabled" || autoBrtState === "off");
  const autoBrtTimeSchedule = autoBrtKnown && autoBrtState === "Time Schedule";
  const visibleBrightnessItems = brightnessItems.filter((it) => {
    if (it.domain === "light") return false;
    const low = (it.name || "").toLowerCase();
    if (autoBrtKnown) {
      if (autoBrtOff && (low.includes("day brightness") || low.includes("night brightness"))) {
        return false;
      }
      if (!autoBrtOff && low.includes("manual brightness")) {
        return false;
      }
      if (
        !autoBrtTimeSchedule &&
        (low.includes("day start hour") || low.includes("night start hour"))
      ) {
        return false;
      }
    }
    return true;
  });
  const homeOrder = ["wake greeting", "weather background", "sun", "moon"];
  const homeItems = sortEntitiesByKeywords(store.getSectionItems("home"), homeOrder);
  const weatherBgSwitch = homeItems.find((it) =>
    (it.name || "").toLowerCase().includes("weather background"),
  );
  const weatherBgOff = weatherBgSwitch ? weatherBgSwitch.state === "off" : false;
  const isCelestialSwitch = (it) =>
    it.domain === "switch" && /^(?:home:\s*)?(?:sun|moon)$/i.test((it.name || "").trim());
  const celestialItems = homeItems.filter(isCelestialSwitch);
  const visibleHomeItems = homeItems.filter((it) => !isCelestialSwitch(it));
  const renderCelestialRow = () =>
    renderSettingsRow({
      id: "weather-celestial-bodies",
      label: "Sun & Moon",
      description: "Choose which sky bodies appear on the live Weather Background.",
      control: html`<div class="pill-list" role="group" aria-label="Sun and Moon">
        ${celestialItems.map((cel) => {
          const st = String(cel.state ?? "");
          const isOn = st === "on";
          const prefKey = cel.pref_key || "";
          const unavailable = !prefKey && (st === "unavailable" || st === "unknown");
          const lbl = entityLabel((cel.name || cel.entity_id).replace(/^home:\s*/i, ""));
          return html`<span class="pill ${isOn ? "enabled" : ""}">
            <button
              type="button"
              aria-pressed=${String(isOn)}
              ?disabled=${unavailable}
              @click=${() => {
                if (prefKey) {
                  store.stageDeviceSetting(prefKey, !isOn);
                } else {
                  void store.espAction(
                    cel.entity_id,
                    isOn ? "turn_off" : "turn_on",
                    isOn ? "off" : "on",
                  );
                }
              }}
              class="pill-toggle"
            >
              ${isOn ? `✓ ${lbl}` : `+ ${lbl}`}
            </button>
          </span>`;
        })}
      </div>`,
    });
  const mediaAppearanceItems = sortEntitiesByKeywords(
    store.getSectionItems("music").filter(isMediaAppearanceEntity),
    ["album art style", "overlay style"],
  );
  const voiceVisualItems = store
    .getSectionItems("voice")
    .filter(isVoiceVisualProfileEntity);
  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : defaultThemeHex(store.host);
  const swatchStyle = `--swatch-color:${curHex}`;
  const screensaverOrder = [
    "docked screensaver",
    "screensaver style",
    "docked idle timeout",
  ];
  const screensaverSleepItems = sortEntitiesByKeywords(
    store.getSectionItems("sleep").filter(isScreensaverSleepEntity),
    screensaverOrder,
  );
  const activateScreensaverBtn = store
    .getSectionItems("actions")
    .find(
      (it) =>
        it.domain === "button" &&
        `${it.name || ""} ${it.entity_id || ""}`.toLowerCase().includes("screensaver"),
    );
  const curCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wallpapers = data?.wallpapers || [];
  const activeWp = wallpapers.find((wp) => Boolean(wp.active)) || null;
  const hasActiveWallpaper = Boolean(activeWp);
  const isRotating = curCycle > 0;
  const starredCount = wallpapers.filter((wp) => Boolean(wp.favorite)).length;
  const allStarred = wallpapers.length > 0 && starredCount === wallpapers.length;
  const wpStatusText = isRotating
    ? `${activeWp ? `${activeWp.name} • rotating` : "Rotating"} ${
        starredCount > 0
          ? `${starredCount} starred wallpaper${starredCount === 1 ? "" : "s"}`
          : `all ${wallpapers.length} wallpapers`
      }.`
    : hasActiveWallpaper
      ? `${activeWp?.name || "Selected"} (static — not rotating).`
      : "Off — click Use on a wallpaper below or enable rotation.";
  const wpRotationHint =
    starredCount === 0
      ? "No wallpapers starred — rotation cycles through all wallpapers."
      : starredCount === 1
        ? "1 wallpaper starred — star at least 2 to cycle between favorites."
        : `${starredCount} of ${wallpapers.length} wallpapers starred for rotation.`;
  return html`<section id="view-display">
    <div class="columns">
      <div class="column">
        ${visibleHomeItems.length || (!weatherBgOff && celestialItems.length > 0)
          ? renderCard({
              heading: html`<h3 class="card-title">Home Screen</h3>`,
              contentClass: "settings-list",
              body: html`<div id="embedded-home" class="settings-list">
                ${visibleHomeItems.map((it) => {
                  const row = renderNativeControlRow(store, it);
                  if (weatherBgSwitch && it.entity_id === weatherBgSwitch.entity_id) {
                    return html`${row}
                      ${!weatherBgOff && celestialItems.length > 0
                        ? renderCelestialRow()
                        : nothing}`;
                  }
                  return row;
                })}
                ${!weatherBgSwitch && !weatherBgOff && celestialItems.length > 0
                  ? renderCelestialRow()
                  : nothing}
              </div>`,
            })
          : nothing}

        ${screensaverSleepItems.length || activateScreensaverBtn
          ? renderCard({
              heading: html`<h3 class="card-title">Screensavers</h3>`,
              contentClass: "settings-list",
              body: html`${screensaverSleepItems.map((it) => renderNativeControlRow(store, it))}
                ${activateScreensaverBtn
                  ? renderSettingsRow({
                      label: entityLabel(
                        activateScreensaverBtn.name || activateScreensaverBtn.entity_id,
                      ),
                      description: "Starts the screensaver on this Device immediately.",
                      control: html`<button
                        type="button"
                        ?disabled=${String(activateScreensaverBtn.state ?? "") === "unavailable"}
                        @click=${() => {
                          const toastMsg = `Triggered "${entityLabel(activateScreensaverBtn.name || activateScreensaverBtn.entity_id)}"`;
                          if (activateScreensaverBtn.device_command) {
                            void store.runDeviceAction(
                              activateScreensaverBtn.device_command,
                              toastMsg,
                            );
                          } else {
                            void store.espAction(
                              activateScreensaverBtn.entity_id,
                              "press",
                              undefined,
                              toastMsg,
                            );
                          }
                        }}
                        class="btn btn-secondary btn-compact"
                      >
                        Preview
                      </button>`,
                    })
                  : nothing}`,
            })
          : nothing}

        ${voiceVisualItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Voice Assistant</h3>`,
              contentClass: "settings-list",
              body: voiceVisualItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}

        ${visibleBrightnessItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Brightness</h3>`,
              contentClass: "settings-list",
              body: visibleBrightnessItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}

        ${clockItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Clock</h3>`,
              contentClass: "settings-list",
              body: clockItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Colors</h3>`,
          contentClass: "settings-list",
          body: html`${colorItems.map((it) => renderNativeControlRow(store, it))}
            ${renderSettingsRow({
              label: "Custom Color",
              forId: "dev-custom-palette-select",
              description: "Used when Color Profile is set to Custom.",
              control: html`<span class="swatch" style=${swatchStyle} aria-hidden="true"></span>
                <select
                  id="dev-custom-palette-select"
                  .value=${curHex}
                  @change=${(ev) => {
                    const val = (ev.currentTarget).value;
                    if (val) store.applyDeviceCustomColor(val, true);
                  }}
                >
                  ${!palettes.length
                    ? html`<option value=${curHex} selected>Current (${curHex})</option>`
                    : html`
                        ${!palettes.some((p) => p.hex.toUpperCase() === curHex)
                          ? html`<option value=${curHex} selected>Current (${curHex})</option>`
                          : nothing}
                        ${palettes.map((p) => {
                          const h = p.hex.toUpperCase();
                          return html`<option value=${h} ?selected=${h === curHex}>
                            ${p.name || h} (${h})
                          </option>`;
                        })}
                      `}
                </select>
                <button
                  type="button"
                  @click=${() => store.openColorWheelModal("device")}
                  class="btn btn-secondary btn-compact"
                >
                  Add Color
                </button>`,
            })}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared presets and uploaded photos cropped for this display.",
          headerActions: renderWallpaperUploadTrigger(store, "device"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "device")}
            <div class="settings-list">
              ${renderSettingsRow({
                id: "wp-status-row",
                label: "Active Wallpaper",
                description: wpStatusText,
                control: isRotating
                  ? html`<button
                        type="button"
                        id="btn-stop-wp-rotation"
                        @click=${() => void store.setWallpaperRotation(0)}
                        class="btn btn-secondary btn-compact"
                      >
                        Stop Rotation
                      </button>
                      <button
                        type="button"
                        id="btn-turn-off-wp"
                        @click=${() => void store.selectWallpaperSource("")}
                        class="btn btn-secondary btn-compact"
                      >
                        Turn Off Wallpaper
                      </button>`
                  : hasActiveWallpaper
                    ? html`${wallpapers.length >= 2
                          ? html`<button
                              type="button"
                              id="btn-enable-wp-rotation"
                              @click=${() => void store.setWallpaperRotation(15)}
                              class="btn btn-secondary btn-compact"
                            >
                              Enable Rotation
                            </button>`
                          : nothing}
                        <button
                          type="button"
                          id="btn-turn-off-wp"
                          @click=${() => void store.selectWallpaperSource("")}
                          class="btn btn-secondary btn-compact"
                        >
                          Turn Off Wallpaper
                        </button>`
                    : wallpapers.length >= 2
                      ? html`<button
                          type="button"
                          id="btn-enable-wp-rotation"
                          @click=${() => void store.setWallpaperRotation(15)}
                          class="btn btn-primary btn-compact"
                        >
                          Enable Rotation
                        </button>`
                      : nothing,
              })}
              ${renderSettingsRow({
                id: "wp-rotation-row",
                label: "Rotation Interval",
                forId: "cfg-wallpaper_cycle_minutes",
                description: wpRotationHint,
                control: html`<select
                    id="cfg-wallpaper_cycle_minutes"
                    aria-label="Wallpaper rotation interval"
                    .value=${String(curCycle)}
                    @change=${(ev) =>
                      void store.setWallpaperRotation(
                        Number((ev.currentTarget).value) || 0,
                      )}
                  >
                    ${WALLPAPER_ROTATION_OPTIONS.map(
                      (opt) =>
                        html`<option value=${String(opt.value)} ?selected=${opt.value === curCycle}>
                          ${opt.label}
                        </option>`,
                    )}
                  </select>
                  ${wallpapers.length > 0 && !allStarred
                    ? html`<button
                        type="button"
                        id="btn-star-all-wp"
                        @click=${() =>
                          void store.setAllWallpaperFavorites(wallpapers.map((w) => w.id))}
                        class="btn btn-text btn-compact"
                      >
                        Star All
                      </button>`
                    : nothing}
                  ${starredCount > 0
                    ? html`<button
                        type="button"
                        id="btn-clear-stars-wp"
                        @click=${() => void store.setAllWallpaperFavorites([])}
                        class="btn btn-text btn-compact"
                      >
                        Clear Stars
                      </button>`
                    : nothing}`,
              })}
            </div>
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(
                store,
                "device",
                wallpapers,
                String(cfg.display_shape || "square"),
              )}
            </div>`,
        })}

        ${mediaAppearanceItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: mediaAppearanceItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-audio-view.ts ---
/**
 * Device Audio & Voice View (`audio_voice`): Voice Assistant, Wake Word, Voice Follows Me, Sound & Music Assistant.
 */
function renderDeviceAudioView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const live = data?.live || {};
  const voiceItems = store.getSectionItems("voice");
  const wwModeItem = voiceItems.find((it) =>
    (it.name || "").toLowerCase().includes("wake word mode"),
  );
  const wwDisabled = wwModeItem ? wwModeItem.state === "Disabled" : false;
  const isWakeWordChoice = (it) =>
    it.key === "wake_word" || it.key === "wake_word_n";
  const voicePrimary = voiceItems.filter((it) => {
    if (it.domain === "assist_satellite") return false;
    if (isVoiceVisualProfileEntity(it)) return false;
    const low = (it.name || "").toLowerCase();
    if (low.includes("cutoff") || low.includes("sensitivity")) return false;
    if (wwDisabled && isWakeWordChoice(it)) return false;
    return true;
  });
  const sensitivityVoiceItems = wwDisabled
    ? []
    : voiceItems.filter(
        (it) =>
          (it.name || "").toLowerCase().includes("cutoff") ||
          (it.name || "").toLowerCase().includes("sensitivity"),
      );
  const soundItems = store.getSectionItems("sound");
  const isRoaming = caps.is_roaming_device !== false;
  const dwellSeconds = Number(cfg.area_follow_dwell_s ?? 10);
  const autoMaEntity = cfg.device_slug ? `media_player.${cfg.device_slug}` : "";
  const savedMa = String(cfg.ma_player_entity || "").trim();
  const maUnmatched = live.ma_link_matched === false;
  const hasCustomMaOverride = Boolean(savedMa && savedMa !== autoMaEntity);
  const showMaOverrideRow = maUnmatched || hasCustomMaOverride;
  const maDescription = maUnmatched
    ? `Automatic match did not find ${autoMaEntity || "this Device's player"} in Music Assistant. Choose this Device's player for library playback, queues and lyrics.`
    : `Linked manually (${autoMaEntity || "default slug"} was not used). Clear to return to automatic matching.`;
  const speakerChoices = data?.catalog?.ma_speakers;
  return html`<section id="view-audio_voice">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Voice Assistant &amp; Wake Word</h3>`,
          contentClass: "settings-list",
          body: html`${voicePrimary.map((it) => renderNativeControlRow(store, it))}
            ${isRoaming
              ? html`${renderSwitchRow({
                    rowId: "row-sync-device-area",
                    id: "cfg-sync_device_area",
                    label: "Voice Follows Me",
                    description:
                      "Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.",
                    checked: Boolean(cfg.sync_device_area),
                    onChange: (checked) =>
                      store.stageDeviceSetting(
                        "sync_device_area",
                        checked,
                        "cfg-sync_device_area",
                      ),
                  })}
                  ${renderSettingsRow({
                    id: "row-area-follow-dwell",
                    label: "Voice Follows Me Delay",
                    forId: "cfg-area_follow_dwell_s",
                    description:
                      "How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).",
                    control: html`<input
                        type="range"
                        id="cfg-area_follow_dwell_s"
                        min="3"
                        max="60"
                        step="1"
                        .value=${String(dwellSeconds)}
                        @change=${(ev) =>
                          store.stageDeviceSetting(
                            "area_follow_dwell_s",
                            Number((ev.currentTarget).value) || 10,
                            "cfg-area_follow_dwell_s",
                          )}
                      />
                      <span id="dwell-value" class="chip">${fmtNumber(dwellSeconds, store.hass, 0)} s</span>`,
                  })}`
              : nothing}
            ${sensitivityVoiceItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Wake Word Sensitivity (Per Model)</summary>
                  <div class="card-content settings-list">
                    ${sensitivityVoiceItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Sound &amp; Playback</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-default_speaker",
              label: "Default Speaker",
              description: "Primary speaker controlled from Music and Home when this Device starts up.",
              value: cfg.default_speaker,
              choices: speakerChoices,
              emptyOptionLabel: "— Automatic (Built-in or Area) —",
              onChange: (val) =>
                store.stageDeviceSetting("default_speaker", val, "cfg-default_speaker"),
            })}
            ${showMaOverrideRow
              ? renderSelectRow({
                  rowId: "row-ma-player-entity",
                  id: "cfg-ma_player_entity",
                  label: "Music Assistant Player",
                  description: maDescription,
                  descId: "desc-ma-player-entity",
                  value: savedMa,
                  choices: data?.catalog?.ma_players,
                  emptyOptionLabel: "— Automatic Match —",
                  onChange: (val) =>
                    store.stageDeviceSetting("ma_player_entity", val, "cfg-ma_player_entity"),
                })
              : nothing}
            ${renderSwitchRow({
              id: "cfg-area_handoff",
              label: "Media Follows This Device to Its New Area",
              description:
                "Transfers active Music Assistant playback when this Device moves to another Area.",
              checked: Boolean(cfg.area_handoff),
              onChange: (checked) =>
                store.stageDeviceSetting("area_handoff", checked, "cfg-area_handoff"),
            })}
            ${soundItems.map((it) => renderNativeControlRow(store, it))}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-interface-view.ts ---
/**
 * Device Interface View (`interface`, D-026 / D-028 / D-030 / D-033 / D-034):
 * Navigation, screen structure & content routing preferences.
 * Column 1: Home Screen (Start Screen & Dock Apps) & Activity Card.
 * Column 2: Area Controls (Area Categories pills), Media Player (Shortcuts & Library Sorting) & Remote Controls.
 */
function renderDeviceInterfaceView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const remoteGroups = data?.system_config?.remote_groups || [];
  const homeDisplayItems = sortEntitiesByKeywords(
    store.getSectionItems("display").filter(isInterfaceDisplayEntity),
    ["start screen"],
  );
  const areaExtraItems = store
    .getSectionItems("area")
    .filter((it) => !(it.name || "").toLowerCase().includes("ble"));
  const enabledAreaCats = store.getEnabledAreaCategories();
  const disabledAreaCats = AREA_CATEGORIES_CATALOG.filter(
    (c) => !enabledAreaCats.includes(c.token),
  );
  const musicItems = store.getSectionItems("music");
  const isMediaShortcutSwitch = (it) =>
    it.domain === "switch" && /\b(speaker|library)\s+shortcut\b/i.test(it.name || it.entity_id);
  const shortcutMusicItems = sortEntitiesByKeywords(
    musicItems.filter(isMediaShortcutSwitch),
    ["speaker shortcut", "library shortcut"],
  );
  const mediaSortOrder = [
    "album sort order",
    "artist album sort order",
    "podcast sort order",
  ];
  const sortMusicItems = sortEntitiesByKeywords(
    musicItems.filter((it) => (it.name || "").toLowerCase().includes("sort")),
    mediaSortOrder,
  );
  const otherMusicNavItems = musicItems.filter(
    (it) =>
      it.domain !== "media_player" &&
      !isMediaAppearanceEntity(it) &&
      !isMediaShortcutSwitch(it) &&
      !(it.name || "").toLowerCase().includes("sort"),
  );
  const remoteEspItems = store.getSectionItems("remote");
  const activityCardOn = cfg.activity_card !== false;
  const enabledSources = new Set(store.getEnabledActivitySources());
  const enabledDock = store.getEnabledDockTokens();
  const disabledDock = DOCK_APPS_CATALOG.filter((a) => !enabledDock.includes(a.token));
  const curDevEntry = (data?.system_devices || []).find(
    (d) => d.subentry_id === store.activeSubentryId,
  );
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  const remoteModeOptions = [
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
  return html`<section id="view-interface">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Home Screen</h3>`,
          contentClass: "settings-list",
          body: html`${homeDisplayItems.map((it) => renderNativeControlRow(store, it))}
            ${renderSettingsRow({
              label: "Dock Apps",
              description: "Toggle and reorder apps shown in the Home Dock.",
              stacked: true,
              control: html`<div id="dock-pills-container" class="pill-list" role="group" aria-label="Dock apps">
                ${enabledDock.map((tok, idx) => {
                  const meta = DOCK_APPS_CATALOG.find((a) => a.token === tok);
                  const lbl = meta ? meta.label : tok;
                  return html`<span class="pill enabled">
                    ${idx > 0
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} left`}
                          @click=${() => store.moveDockAppToken(tok, -1)}
                          class="pill-move"
                        >
                          ‹
                        </button>`
                      : nothing}
                    <button
                      type="button"
                      aria-pressed="true"
                      @click=${() => store.toggleDockAppToken(tok)}
                      class="pill-toggle"
                    >
                      ✓ ${lbl}
                    </button>
                    ${idx < enabledDock.length - 1
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} right`}
                          @click=${() => store.moveDockAppToken(tok, 1)}
                          class="pill-move"
                        >
                          ›
                        </button>`
                      : nothing}
                  </span>`;
                })}
                ${disabledDock.map(
                  (app) => html`<span class="pill">
                    <button
                      type="button"
                      aria-pressed="false"
                      @click=${() => store.toggleDockAppToken(app.token)}
                      class="pill-toggle"
                    >
                      + ${app.label}
                    </button>
                  </span>`,
                )}
              </div>`,
            })}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Activity Card</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              labelHtml: html`<label for="cfg-activity_card" class="row-label">Show the Activity Card</label>`,
              description:
                "Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.",
              control: html`<input
                type="checkbox"
                id="cfg-activity_card"
                role="switch"
                .checked=${activityCardOn}
                @change=${(ev) =>
                  store.stageDeviceSetting(
                    "activity_card",
                    (ev.currentTarget).checked,
                    "cfg-activity_card",
                  )}
                class="switch"
              />`,
            })}
            ${activityCardOn
              ? renderSettingsRow({
                  id: "activity-sources",
                  label: "Activity Card Sources",
                  description: "Choose which live items appear in the Activity Card.",
                  stacked: true,
                  control: html`<div class="pill-list" role="group" aria-label="Activity Card sources">
                    ${ACTIVITY_SOURCES_CATALOG.map((src) => {
                      const on = enabledSources.has(src.id);
                      return html`<span
                        data-src=${src.id}
                        data-label=${src.label}
                        class="pill ${on ? "enabled" : ""}"
                      >
                        <button
                          type="button"
                          aria-pressed=${String(on)}
                          @click=${() => store.toggleActivitySource(src.id)}
                          class="pill-toggle"
                        >
                          ${on ? `✓ ${src.label}` : `+ ${src.label}`}
                        </button>
                      </span>`;
                    })}
                  </div>`,
                })
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Area Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
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
            ${areaExtraItems.map((it) => renderNativeControlRow(store, it))}`,
        })}

        ${shortcutMusicItems.length || sortMusicItems.length || otherMusicNavItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: html`${shortcutMusicItems.length
                  ? renderSettingsRow({
                      id: "media-player-shortcuts",
                      label: "Shortcuts",
                      description:
                        "Choose which quick-access buttons appear on the Music player screen.",
                      control: html`<div
                        class="pill-list"
                        role="group"
                        aria-label="Media Player shortcuts"
                      >
                        ${shortcutMusicItems.map((sc) => {
                          const st = String(sc.state ?? "");
                          const isOn = st === "on";
                          const prefKey = sc.pref_key || "";
                          const unavailable =
                            !prefKey && (st === "unavailable" || st === "unknown");
                          const rawShort = (sc.name || sc.entity_id)
                            .replace(/^music:\s*/i, "")
                            .replace(/^show\s+/i, "")
                            .replace(/\s+shortcut$/i, "")
                            .trim();
                          const lbl = entityLabel(rawShort || sc.name || sc.entity_id);
                          return html`<span class="pill ${isOn ? "enabled" : ""}">
                            <button
                              type="button"
                              aria-pressed=${String(isOn)}
                              ?disabled=${unavailable}
                              @click=${() => {
                                if (prefKey) {
                                  store.stageDeviceSetting(prefKey, !isOn);
                                } else {
                                  void store.espAction(
                                    sc.entity_id,
                                    isOn ? "turn_off" : "turn_on",
                                    isOn ? "off" : "on",
                                  );
                                }
                              }}
                              class="pill-toggle"
                            >
                              ${isOn ? `✓ ${lbl}` : `+ ${lbl}`}
                            </button>
                          </span>`;
                        })}
                      </div>`,
                    })
                  : nothing}
                ${sortMusicItems.map((it) => renderNativeControlRow(store, it))}
                ${otherMusicNavItems.map((it) => renderNativeControlRow(store, it))}`,
            })
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Remote Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-device_remote_group",
              label: "Remote Control Group",
              description: "Choose which remotes appear on this Device's Remote screen.",
              value: curRemoteMode,
              rawOptions: remoteModeOptions,
              onChange: (val) =>
                store.stageDeviceSetting(
                  "device_remote_group",
                  val,
                  "cfg-device_remote_group",
                ),
            })}
            ${remoteEspItems.map((it) => renderNativeControlRow(store, it))}`,
          footerActions: html`<button
            type="button"
            @click=${() => store.openSystemSection("remotes")}
            class="btn btn-text"
          >
            Manage Remote Groups
          </button>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-overview-view.ts ---
/**
 * Device Overview View (`dashboard`, D-029): Health repairs alert, high-level Status card
 * (header state pill, 2x2 tonal metric tiles, clickable assignment summary rows + footer),
 * Quick Actions & Sensors.
 */
const ICON_AREA = "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const ICON_BATTERY = "M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z";
const ICON_PLUG = "M16,7V3H14V7H10V3H8V7H8C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7M16,13.67L12.5,17.17V19H11.5V17.17L8,13.67V9H16V13.67Z";
const ICON_RADAR = "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const ICON_WIFI = "M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z";
const ICON_BLUETOOTH = "M14.88,16.29L13,18.17V14.41M13,5.83L14.88,7.71L13,9.58M17.71,7.71L12,2H11V9.58L6.41,5L5,6.41L10.59,12L5,17.58L6.41,19L11,14.41V22H12L17.71,16.29L13.41,12L17.71,7.71Z";
const ICON_CHIP = "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";
const ICON_TAG = "M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.9,2 2,2.9 2,4V11C2,11.55 2.22,12.05 2.59,12.42L11.59,21.42C11.95,21.78 12.45,22 13,22C13.55,22 14.05,21.78 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.45 21.77,11.94 21.41,11.58M13,20.01L4,11V4H11V3.99L20,12.99L13,20.01M6.5,5A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 6.5,8A1.5,1.5 0 0,1 5,6.5A1.5,1.5 0 0,1 6.5,5Z";
function renderTileIcon(pathD) {
  return html`<svg viewBox="0 0 24 24" aria-hidden="true"><path d=${pathD}></path></svg>`;
}
function rssiQualityLabel(rssi) {
  if (rssi === null || !Number.isFinite(rssi)) return "No reading";
  if (rssi >= -60) return "Excellent";
  if (rssi >= -70) return "Good";
  if (rssi >= -80) return "Fair";
  return "Weak";
}
function renderDeviceOverviewView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const caps = data?.capabilities || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const deviceIssues = (data?.issues || []).filter(
    (i) => i.subentry_id && i.subentry_id === store.activeSubentryId,
  );
  const hasErrorIssue = deviceIssues.some(
    (i) => i.severity === "error" || i.severity === "critical",
  );
  // Live Status calculations
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  const hasBatteryReading =
    !isBleOnly &&
    curDevEntry?.battery_level !== null &&
    curDevEntry?.battery_level !== undefined &&
    Number.isFinite(Number(curDevEntry.battery_level));
  const batPct = hasBatteryReading
    ? Math.max(0, Math.min(100, Math.round(Number(curDevEntry?.battery_level))))
    : 0;
  const batMeta = curDevEntry?.is_charging
    ? "Charging"
    : curDevEntry?.is_usb_connected
      ? "Plugged in"
      : "On battery";
  let rssiVal = null;
  if (!isBleOnly && curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
    rssiVal = Number(curDevEntry.wifi_rssi);
  } else if (isBleOnly && winRow && winRow.effective_rssi !== null && winRow.effective_rssi !== undefined) {
    rssiVal = Number(winRow.effective_rssi);
  }
  const hasRssi = rssiVal !== null && Number.isFinite(rssiVal);
  const rssiText = hasRssi ? `${fmtNumber(rssiVal, store.hass, 0)} dBm` : "—";
  const rssiPct = hasRssi ? rssiToPercent(rssiVal) : 0;
  const hasAssignedArea = Boolean(curDevEntry?.has_assigned_area);
  const areaText = hasAssignedArea
    ? curDevEntry?.area_label || live.active_area_name || "—"
    : live.active_area_name || "—";
  const distSuffix =
    live.ble_closest_proxy && winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
      ? ` (~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)})`
      : "";
  const showProxyMeta = Boolean(!isBleOnly && caps.has_ble_beacon && cfg.native_ble_tracking && live.ble_closest_proxy);
  const areaMetaBase = isBleOnly ? "BLE tag" : hasAssignedArea ? "Stationary" : "Roaming";
  const areaMeta = showProxyMeta
    ? `${areaMetaBase} • ${live.ble_closest_proxy}${distSuffix}`
    : areaMetaBase;
  const rawSw = String(live.device_sw_version || esp?.device?.sw_version || "").replace(/^v/i, "");
  const fwValue = rawSw ? `v${rawSw}` : "—";
  const fwMeta = live.fw_update_available
    ? "Update available"
    : rawSw
      ? "Up to date"
      : "Not reported";
  let statusChipClass = "chip";
  let statusDotClass = "status-dot";
  let statusLabel = "—";
  if (isBleOnly) {
    statusLabel = curDevEntry?.status_label || "—";
    const detected = statusLabel.toLowerCase().includes("detected") || Boolean(winRow);
    if (detected) {
      statusChipClass = "chip chip-success";
      statusDotClass = "status-dot online";
    }
  } else if (curDevEntry?.is_online && live.fw_update_available) {
    statusChipClass = "chip chip-warning";
    statusDotClass = "status-dot update";
    statusLabel = "Update available";
  } else if (curDevEntry?.is_online) {
    statusChipClass = "chip chip-success";
    statusDotClass = "status-dot online";
    statusLabel = "Online";
  } else if (curDevEntry?.is_online === false) {
    statusLabel = "Offline";
  }
  const quickActionItems = store
    .getSectionItems("actions")
    .concat(store.getSectionItems("overview"));
  const quickActionButtons = quickActionItems.filter((it) => it.domain === "button");
  const otherQuickItems = quickActionItems.filter((it) => it.domain !== "button");
  const otherSensorItems = store.getSectionItems("other");
  const groups = data?.device_groups || [];
  const curGroupId = cfg.device_group || "unassigned";
  const curGroupName =
    groups.find((g) => g.id === curGroupId)?.name ||
    (curGroupId === "unassigned" ? "Unassigned" : curGroupId);
  const syncStatus = live.group_sync_status ?? curDevEntry?.group_sync_status;
  const isCustomized = curGroupId !== "unassigned" && isGroupCustomized(syncStatus);
  const remoteGroups = data?.system_config?.remote_groups || [];
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  let remoteSummary = "Follow Area";
  if (curRemoteMode === "all") {
    remoteSummary = "All System Remotes";
  } else if (curRemoteMode.startsWith("group:")) {
    const gid = curRemoteMode.slice(6);
    remoteSummary = remoteGroups.find((g) => g.id === gid)?.name || gid;
  }
  const powerTileBody = hasBatteryReading
    ? html`<div class="status-tile-head">
          ${renderTileIcon(ICON_BATTERY)}
          <span>Battery</span>
        </div>
        <strong class="status-tile-value">${fmtPercent(curDevEntry?.battery_level, store.hass)}</strong>
        <span class="status-tile-meta">${batMeta}</span>
        <div class="signal-track" aria-hidden="true">
          <div
            class="signal-fill${batPct <= 20 && !curDevEntry?.is_charging ? " low" : ""}"
            style=${`--signal-pct:${batPct}%`}
          ></div>
        </div>`
    : html`<div class="status-tile-head">
          ${renderTileIcon(ICON_PLUG)}
          <span>Power</span>
        </div>
        <strong class="status-tile-value">Plugged in</strong>
        <span class="status-tile-meta">${caps.has_power ? "Sleep & wake active" : "Always on"}</span>`;
  return html`<section id="view-dashboard" class="stack">
    ${deviceIssues.length
      ? html`<div role="alert" class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}">
          <div class="alert-body">
            <strong>Needs Attention</strong>
            <ul class="alert-list">
              ${deviceIssues.map((iss) => html`<li>${issueMessage(iss)}</li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            Open Repairs
          </button>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Status</h3>`,
          headerActions: html`<span id="st-status-chip" class=${statusChipClass}>
            <span class=${statusDotClass} aria-hidden="true"></span>${statusLabel}
          </span>`,
          contentClass: "stack",
          body: html`<div class="status-tiles">
              <button
                type="button"
                @click=${() => store.switchView("presence")}
                class="status-tile"
              >
                <div class="status-tile-head">
                  ${renderTileIcon(ICON_AREA)}
                  <span id="st-area-label">${hasAssignedArea ? "Area" : "Current Area"}</span>
                </div>
                <strong class="status-tile-value">${areaText}</strong>
                <span class="status-tile-meta">${areaMeta}</span>
              </button>

              ${isBleOnly
                ? html`<button
                    type="button"
                    @click=${() => store.switchView("presence")}
                    class="status-tile"
                  >
                    <div class="status-tile-head">
                      ${renderTileIcon(ICON_RADAR)}
                      <span>Closest Proxy</span>
                    </div>
                    <strong class="status-tile-value">${live.ble_closest_proxy || "—"}</strong>
                    <span class="status-tile-meta">
                      ${winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
                        ? `~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)}`
                        : "BLE presence"}
                    </span>
                  </button>`
                : hasBatteryReading || caps.has_power
                  ? html`<button
                      type="button"
                      @click=${() => store.switchView("power")}
                      class="status-tile"
                    >
                      ${powerTileBody}
                    </button>`
                  : html`<div class="status-tile">${powerTileBody}</div>`}

              <button
                type="button"
                @click=${() => store.switchView(isBleOnly ? "presence" : "tools")}
                class="status-tile"
              >
                <div class="status-tile-head">
                  ${renderTileIcon(isBleOnly ? ICON_BLUETOOTH : ICON_WIFI)}
                  <span id="st-wifi-label">${isBleOnly ? "BLE Signal" : "Wi-Fi Signal"}</span>
                </div>
                <strong class="status-tile-value">${rssiText}</strong>
                <span class="status-tile-meta">${rssiQualityLabel(rssiVal)}</span>
                ${hasRssi
                  ? html`<div class="signal-track" aria-hidden="true">
                      <div
                        class="signal-fill${rssiVal !== null && rssiVal < -80 ? " low" : ""}"
                        style=${`--signal-pct:${rssiPct}%`}
                      ></div>
                    </div>`
                  : nothing}
              </button>

              ${isBleOnly
                ? html`<button
                    type="button"
                    @click=${() => store.switchView("presence")}
                    class="status-tile"
                  >
                    <div class="status-tile-head">
                      ${renderTileIcon(ICON_TAG)}
                      <span>BLE Target</span>
                    </div>
                    <strong class="status-tile-value">
                      <code>${cfg.ble_target_address || "—"}</code>
                    </strong>
                    <span class="status-tile-meta">Bluetooth address</span>
                  </button>`
                : html`<button
                    type="button"
                    @click=${() => store.switchView("tools")}
                    class="status-tile"
                  >
                    <div class="status-tile-head">
                      ${renderTileIcon(ICON_CHIP)}
                      <span>Firmware</span>
                    </div>
                    <strong class="status-tile-value">${fwValue}</strong>
                    <span class="status-tile-meta">${fwMeta}</span>
                  </button>`}
            </div>

            ${!isBleOnly
              ? html`<div class="kv-list status-assignments">
                  <button
                    type="button"
                    @click=${() => store.openSystemSection("system_sync")}
                    class="kv-row"
                  >
                    <span>Device Group</span>
                    <strong>
                      ${curGroupId !== "unassigned"
                        ? html`<span
                            class="chip ${isCustomized ? "chip-warning" : "chip-success"}"
                          >
                            ${isCustomized ? "Customized" : "In Sync"}
                          </span>`
                        : nothing}${curGroupName}
                    </strong>
                  </button>
                  ${caps.has_display
                    ? html`<button
                        type="button"
                        @click=${() => store.switchView("interface")}
                        class="kv-row"
                      >
                        <span>Remote Group</span>
                        <strong>${remoteSummary}</strong>
                      </button>`
                    : nothing}
                </div>`
              : nothing}`,
          footerActions: html`${links.esphome_device_id
              ? html`<button
                  type="button"
                  id="btn-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in ESPHome
                </button>`
              : nothing}
            <button
              type="button"
              @click=${() => void store.exportBackup(store.activeSubentryId)}
              class="btn btn-text"
            >
              Download Backup
            </button>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Quick Actions",
          contentClass: "settings-list",
          body: html`${renderQuickActionGrid(store, quickActionButtons)}
            ${!isBleOnly
              ? renderSettingsRow({
                  label: "Device Group",
                  forId: "cfg-device_group",
                  description:
                    "Shares operational behavior (sleep, wake word, BLE) across matching Devices.",
                  control: html`${curGroupId !== "unassigned"
                      ? html`<span
                          id="dash-group-sync-chip"
                          class="chip ${isCustomized ? "chip-warning" : "chip-success"}"
                        >
                          ${isCustomized ? "Customized" : "In Sync"}
                        </span>`
                      : nothing}
                    <select
                      id="cfg-device_group"
                      .value=${curGroupId}
                      @change=${(ev) =>
                        store.stageDeviceSetting(
                          "device_group",
                          (ev.currentTarget).value,
                          "cfg-device_group",
                        )}
                    >
                      ${groups.map(
                        (g) =>
                          html`<option value=${g.id} ?selected=${g.id === curGroupId}>
                            ${g.name}
                          </option>`,
                      )}
                    </select>
                    ${isCustomized
                      ? html`<button
                          type="button"
                          id="btn-reset-to-group"
                          @click=${() => void store.syncDeviceGroup(curGroupId, store.activeSubentryId)}
                          class="btn btn-secondary btn-compact"
                        >
                          Reset to Group
                        </button>`
                      : nothing}`,
                })
              : nothing}
            ${renderSelectRow({
              id: "cfg-assigned_person",
              label: "Assigned Person",
              description: "Links this Device's Area presence to a Home Assistant person entity.",
              value: cfg.assigned_person,
              choices: data?.catalog?.persons,
              emptyOptionLabel: "— Unassigned —",
              onChange: (val) =>
                store.stageDeviceSetting("assigned_person", val, "cfg-assigned_person"),
            })}
            ${otherQuickItems.map((it) => renderNativeControlRow(store, it))}`,
        })}

        ${otherSensorItems.length
          ? renderCard({
              title: "Sensors & Controls",
              contentClass: "settings-list",
              body: otherSensorItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-power-view.ts ---
/**
 * Device Power View (`power`, D-014 / D-027): Sleep & Wake controls and Power & Battery telemetry.
 */
function renderDevicePowerView(store) {
  const sleepItems = store
    .getSectionItems("sleep")
    .filter((it) => !isScreensaverSleepEntity(it));
  const batteryItems = store.getSectionItems("battery");
  const bothEmpty = !sleepItems.length && !batteryItems.length;
  return html`<section id="view-power">
    <div class="columns">
      <div class="column">
        ${sleepItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Sleep &amp; Wake</h3>
              </div>
              <div class="card-content settings-list">
                ${sleepItems.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : bothEmpty
            ? renderCard({
                title: "Power & Battery",
                body: html`<p class="empty-state">
                  No sleep or battery entities reported by this Device.
                </p>`,
              })
            : nothing}
      </div>
      <div class="column">
        ${batteryItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Power &amp; Battery</h3>
              </div>
              <div class="card-content settings-list">
                ${batteryItems.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-presence-view.ts ---
/**
 * Device BLE & Area Presence View (`presence`): Static Assigned Area vs. BLE Roaming, Fallback Area, and BLE Identity.
 */
function renderDevicePresenceView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const isBleOnly = cfg.kind === "ble_tag";
  const bleTracking = isBleOnly || Boolean(cfg.native_ble_tracking);
  const bleAreaItems = store
    .getSectionItems("area")
    .filter((it) => (it.name || "").toLowerCase().includes("ble"));
  return html`<section id="view-presence">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Area Tracking",
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? renderSwitchRow({
                  id: "cfg-native_ble_tracking",
                  label: "Track the Area with BLE Proxies",
                  description:
                    "Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically. Turn off to pin it to one assigned Area.",
                  checked: Boolean(cfg.native_ble_tracking),
                  onChange: (checked) =>
                    store.stageDeviceSetting(
                      "native_ble_tracking",
                      checked,
                      "cfg-native_ble_tracking",
                    ),
                })
              : nothing}
            ${bleTracking
              ? html`${!isBleOnly
                    ? renderSwitchRow({
                        id: "cfg-ble_auto_switch",
                        label: "Auto-Switch Active Area",
                        description:
                          "Switches the Device's active Area controls automatically when BLE detects a move.",
                        checked: Boolean(cfg.ble_auto_switch),
                        onChange: (checked) =>
                          store.stageDeviceSetting(
                            "ble_auto_switch",
                            checked,
                            "cfg-ble_auto_switch",
                          ),
                      })
                    : nothing}
                  ${renderSelectRow({
                    id: "cfg-default_area",
                    label: "Fallback Area",
                    description:
                      "Default Home Assistant Area when no Bluetooth proxy is in range.",
                    value: cfg.default_area,
                    choices: data?.catalog?.areas,
                    emptyOptionLabel: "— Automatic (ESPHome Area) —",
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "default_area",
                        val,
                        "cfg-default_area",
                      ),
                  })}
                  ${bleAreaItems.map((it) => renderNativeControlRow(store, it))}`
              : renderSelectRow({
                  id: "cfg-default_area",
                  label: "Assigned Area",
                  description:
                    "Pins this Device's Area controls and Home Assistant Device Area to one location.",
                  value: cfg.default_area,
                  choices: data?.catalog?.areas,
                  emptyOptionLabel: "— Unassigned —",
                  onChange: (val) =>
                    store.stageDeviceSetting(
                      "default_area",
                      val,
                      "cfg-default_area",
                    ),
                })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "BLE Identity",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="cfg-ble_target_address">BLE Target Address or Entity</label>
              <input
                type="text"
                id="cfg-ble_target_address"
                placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
                .value=${String(cfg.ble_target_address || "")}
                @change=${(ev) =>
                  store.stageDeviceSetting(
                    "ble_target_address",
                    (ev.currentTarget).value.trim(),
                    "cfg-ble_target_address",
                  )}
              />
              <span class="help-text">
                Leave blank on Latter displays to track their built-in BLE beacon MAC automatically.
              </span>
            </div>
            ${!isBleOnly
              ? html`<div class="stacked-field">
                  <label for="cfg-ble_beacon_uuid">iBeacon UUID</label>
                  <input
                    type="text"
                    id="cfg-ble_beacon_uuid"
                    placeholder="Generated automatically per System"
                    .value=${String(cfg.ble_beacon_uuid || "")}
                    @change=${(ev) =>
                      store.stageDeviceSetting(
                        "ble_beacon_uuid",
                        (ev.currentTarget).value.trim(),
                        "cfg-ble_beacon_uuid",
                      )}
                  />
                </div>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-tools-view.ts ---
/**
 * Device Tools View (`tools`, D-027): Standard Diagnostics + collapsed Developer & Telemetry drawer,
 * Perimeter Security Policy + write-only PIN, Replace Hardware & Danger Zone.
 */
const INTERACTIVE_ENTITY_DOMAINS = new Set([
  "update",
  "button",
  "switch",
  "select",
  "number",
]);
function isValidTelemetryState(val) {
  const s = String(val ?? "").trim();
  return s !== "" && s !== "unknown" && s !== "unavailable";
}
function isInternalNetworkBlobEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("rpc outbox") ||
    low.includes("rpc_outbox") ||
    low.includes("hardware manifest") ||
    low.includes("hardware_manifest") ||
    low.includes("link report") ||
    low.includes("link_report")
  );
}
function isSummaryDuplicateNetworkEntity(it) {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("wifi signal") ||
    low.includes("wi-fi signal") ||
    low.includes("wifi_signal") ||
    low.includes("ip address") ||
    low.includes("ip_address") ||
    low.includes("mac address") ||
    low.includes("mac_address") ||
    low.includes("firmware version") ||
    low.includes("firmware_version") ||
    low.includes("latter sdk")
  );
}
function formatTelemetryDuration(totalSec) {
  if (!Number.isFinite(totalSec) || totalSec < 0) return "—";
  const secs = Math.round(totalSec);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) {
    const remSec = secs % 60;
    return remSec > 0 ? `${mins}m ${remSec}s` : `${mins}m`;
  }
  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    const remMin = mins % 60;
    return remMin > 0 ? `${hours}h ${remMin}m` : `${hours}h`;
  }
  const days = Math.floor(hours / 24);
  const remHr = hours % 24;
  return remHr > 0 ? `${days}d ${remHr}h` : `${days}d`;
}
function parseDeviceLinkReportRows(
  rawState,
  hass,
) {
  if (!isValidTelemetryState(rawState)) return [];
  const kv = new Map();
  for (const tok of rawState.trim().split(/\s+/)) {
    const eq = tok.indexOf("=");
    if (eq > 0 && eq < tok.length - 1) {
      kv.set(tok.slice(0, eq), tok.slice(eq + 1));
    }
  }
  if (!kv.size) return [];
  const rows = [];
  const upRaw = kv.get("up");
  if (upRaw !== undefined && Number.isFinite(Number(upRaw))) {
    rows.push({
      label: "Session Uptime",
      value: formatTelemetryDuration(Number(upRaw)),
    });
  }
  const rstRaw = kv.get("rst");
  if (rstRaw) {
    rows.push({ label: "Last Reset", value: rstRaw, code: true });
  }
  const discRaw = kv.get("disc");
  if (discRaw !== undefined && Number.isFinite(Number(discRaw))) {
    const btoNum = Number(kv.get("bto") ?? 0);
    const btoSuffix =
      Number.isFinite(btoNum) && btoNum > 0
        ? ` (${fmtNumber(btoNum, hass, 0)} beacon timeouts)`
        : "";
    rows.push({
      label: "Wi-Fi Disconnects",
      value: `${fmtNumber(Number(discRaw), hass, 0)}${btoSuffix}`,
    });
  }
  const rssiRaw = kv.get("rssi");
  if (rssiRaw && rssiRaw !== "na" && rssiRaw.includes("/")) {
    const [avgStr, minStr] = rssiRaw.split("/", 2);
    if (Number.isFinite(Number(avgStr)) && Number.isFinite(Number(minStr))) {
      rows.push({
        label: "Wi-Fi Avg / Min",
        value: `${fmtNumber(Number(avgStr), hass, 0)} / ${fmtNumber(Number(minStr), hass, 0)} dBm`,
      });
    }
  }
  const haRaw = kv.get("ha");
  if (haRaw !== undefined && Number.isFinite(Number(haRaw))) {
    const gapNum = Number(kv.get("gap") ?? 0);
    const gapSuffix =
      Number.isFinite(gapNum) && gapNum > 0
        ? ` (max gap ${formatTelemetryDuration(gapNum)})`
        : "";
    rows.push({
      label: "HA Sessions",
      value: `${fmtNumber(Number(haRaw), hass, 0)}${gapSuffix}`,
    });
  }
  const slpRaw = kv.get("slp");
  if (slpRaw !== undefined && Number.isFinite(Number(slpRaw))) {
    const lsNum = Number(kv.get("ls") ?? 0);
    const lsSuffix =
      Number.isFinite(lsNum) && lsNum > 0
        ? ` (${fmtNumber(lsNum, hass, 0)} cycles)`
        : "";
    rows.push({
      label: "Light Sleep Duty",
      value: `${fmtNumber(Number(slpRaw), hass, 1)}%${lsSuffix}`,
    });
  }
  const nvsRaw = kv.get("nvs");
  if (nvsRaw && nvsRaw.includes("/")) {
    const parts = nvsRaw.split("/");
    if (parts.length >= 3 && parts.every((p) => Number.isFinite(Number(p)))) {
      rows.push({
        label: "NVS Flash Writes",
        value: `${fmtNumber(Number(parts[0]), hass, 0)} writes (${fmtNumber(Number(parts[1]), hass, 0)} erases, ${fmtNumber(Number(parts[2]), hass, 0)} ms max)`,
      });
    }
  }
  return rows;
}
function parseDeviceHardwareManifestRows(
  rawState,
  hass,
) {
  if (!isValidTelemetryState(rawState)) return [];
  const trimmed = rawState.trim();
  if (!trimmed.startsWith("{")) return [];
  let parsed;
  try {
    const obj = JSON.parse(trimmed);
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
    parsed = obj;
  } catch {
    return [];
  }
  const rows = [];
  const board = typeof parsed.board === "string" ? parsed.board.trim() : "";
  if (board) {
    rows.push({ label: "Hardware Board", value: board, code: true });
  }
  const chip = typeof parsed.chip === "string" ? parsed.chip.trim() : "";
  const psramMb = Number(parsed.psram_mb ?? 0);
  if (chip) {
    const psramSuffix =
      Number.isFinite(psramMb) && psramMb > 0
        ? ` • ${fmtNumber(psramMb, hass, 0)} MB PSRAM`
        : "";
    rows.push({ label: "Processor & PSRAM", value: `${chip}${psramSuffix}` });
  }
  const hasDisplay = Number(parsed.display ?? 0) === 1 && parsed.shape !== "none";
  if (parsed.display !== undefined) {
    if (!hasDisplay) {
      rows.push({ label: "Display Panel", value: "Headless" });
    } else {
      const w = Number(parsed.w ?? 0);
      const h = Number(parsed.h ?? 0);
      const shape = typeof parsed.shape === "string" ? parsed.shape.trim() : "";
      const panelTech =
        parsed.ips === 1 ? "IPS" : parsed.ips === 0 ? "AMOLED" : "";
      if (w > 0 && h > 0) {
        const parts = [`${w}×${h}`, shape, panelTech].filter(Boolean);
        rows.push({ label: "Display Panel", value: parts.join(" ") });
      }
    }
  }
  const traits = [];
  if (Number(parsed.touch) === 1) traits.push("Touch");
  if (Number(parsed.mic) === 1) traits.push("Mic");
  if (Number(parsed.spk) === 1) traits.push("Speaker");
  if (Number(parsed.mic) !== 1 && Number(parsed.spk) !== 1 && Number(parsed.audio) === 1) {
    traits.push("Audio");
  }
  if (Number(parsed.imu) === 1) traits.push("IMU");
  if (Number(parsed.battery) === 1) traits.push("Battery");
  if (Number(parsed.wearable) === 1) traits.push("Wearable");
  if (Number(parsed.stationary) === 1) traits.push("Stationary");
  if (traits.length) {
    rows.push({ label: "Hardware Traits", value: traits.join(", ") });
  }
  return rows;
}
function renderDeviceToolsView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const networkItems = store.getSectionItems("network");
  const developerItems = store.getSectionItems("developer");
  const networkControlItems = networkItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const extraNetworkSensorItems = networkItems.filter(
    (it) =>
      !INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !isInternalNetworkBlobEntity(it) &&
      !isSummaryDuplicateNetworkEntity(it),
  );
  const findNetworkState = (keyword) => {
    const match = networkItems.find((it) =>
      `${it.name || ""} ${it.entity_id || ""}`.toLowerCase().includes(keyword),
    );
    return isValidTelemetryState(match?.state) ? String(match?.state).trim() : "";
  };
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  let signalText = "—";
  if (!isBleOnly) {
    if (curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
      signalText = `${fmtNumber(curDevEntry.wifi_rssi, store.hass, 0)} dBm`;
    } else {
      const rawWifi = findNetworkState("wifi signal") || findNetworkState("wi-fi signal");
      if (rawWifi) {
        signalText = Number.isFinite(Number(rawWifi))
          ? `${fmtNumber(Number(rawWifi), store.hass, 0)} dBm`
          : rawWifi;
      }
    }
  } else if (winRow && winRow.effective_rssi !== null) {
    signalText = `${fmtNumber(winRow.effective_rssi, store.hass, 0)} dBm`;
  }
  const rawSw = String(
    live.device_sw_version || esp?.device?.sw_version || findNetworkState("firmware version") || "",
  ).replace(/^v/i, "");
  const fwVersionText = rawSw ? `v${rawSw}` : "—";
  const modelText = curDevEntry?.model_label || esp?.device?.model || "—";
  const ipStr = curDevEntry?.ip_address || findNetworkState("ip address") || "";
  const macStr = esp?.device?.mac || findNetworkState("mac address") || "";
  const devControlItems = developerItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const devSensorItems = developerItems.filter(
    (it) => !INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const linkReportEntity = networkItems.find((it) => {
    const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
    return low.includes("link report") || low.includes("link_report");
  });
  const manifestEntity = networkItems.find((it) => {
    const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
    return low.includes("hardware manifest") || low.includes("hardware_manifest");
  });
  const linkRows = parseDeviceLinkReportRows(linkReportEntity?.state, store.hass);
  const manifestRows = parseDeviceHardwareManifestRows(manifestEntity?.state, store.hass);
  const hasDeveloperDrawer =
    !isBleOnly &&
    Boolean(
      devControlItems.length ||
        devSensorItems.length ||
        linkRows.length ||
        manifestRows.length,
    );
  const curPinPolicy = String(cfg.security_pin_policy || "auto");
  const hasPin = store.hasConfiguredSecurityPin;
  return html`<section id="view-tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Diagnostics</h3>`,
          contentClass: "stack",
          body: html`${networkControlItems.length
              ? html`<div class="settings-list">
                  ${networkControlItems.map((it) => renderNativeControlRow(store, it))}
                </div>`
              : nothing}
            <div class="kv-list">
              ${isBleOnly
                ? html`<div class="kv-row">
                      <span>BLE Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>BLE Target</span>
                      <strong>${cfg.ble_target_address ? html`<code>${cfg.ble_target_address}</code>` : "—"}</strong>
                    </div>`
                : html`<div class="kv-row">
                      <span>Model</span>
                      <strong>${modelText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>ESPHome Node</span>
                      <strong><code id="diag-node-name">${cfg.device_slug || "—"}</code></strong>
                    </div>
                    <div class="kv-row">
                      <span>Firmware Version</span>
                      <strong>${fwVersionText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Latter SDK</span>
                      <strong id="diag-sdk-rev">${live.sdk_rev || "—"}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Wi-Fi Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>IP Address</span>
                      <strong>${ipStr ? html`<code>${ipStr}</code>` : "—"}</strong>
                    </div>
                    ${macStr
                      ? html`<div class="kv-row">
                          <span>MAC Address</span>
                          <strong><code>${macStr}</code></strong>
                        </div>`
                      : nothing}
                    ${extraNetworkSensorItems.map((it) => renderNativeControlRow(store, it))}`}
            </div>
            ${links.latter_device_id || links.entry_id
              ? html`<div class="settings-list">
                  ${renderSettingsRow({
                    id: "row-diagnostics",
                    label: "Diagnostics File",
                    description: "Downloads redacted Home Assistant diagnostics for troubleshooting.",
                    control: html`<button
                      type="button"
                      @click=${() => void store.downloadDeviceDiagnostics()}
                      class="btn btn-secondary btn-compact"
                    >
                      Download Diagnostics
                    </button>`,
                  })}
                </div>`
              : nothing}
            ${hasDeveloperDrawer
              ? html`<details class="sub-collapsible">
                  <summary>Developer &amp; Telemetry</summary>
                  <div class="card-content">
                    ${devControlItems.length
                      ? html`<div class="settings-list">
                          ${devControlItems.map((it) => renderNativeControlRow(store, it))}
                        </div>`
                      : nothing}
                    ${devSensorItems.length || linkRows.length || manifestRows.length
                      ? html`<div class="kv-list">
                          ${devSensorItems.map((it) => renderNativeControlRow(store, it))}
                          ${[...linkRows, ...manifestRows].map(
                            (row) => html`<div class="kv-row">
                              <span>${row.label}</span>
                              <strong>${row.code ? html`<code>${row.value}</code>` : row.value}</strong>
                            </div>`,
                          )}
                        </div>`
                      : nothing}
                  </div>
                </details>`
              : nothing}`,
          footerActions:
            !isBleOnly && (links.esphome_device_id || links.latter_device_id)
              ? html`<button
                  type="button"
                  id="btn-tools-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in ESPHome
                </button>`
              : nothing,
        })}
      </div>

      <div class="column">
        ${!isBleOnly
          ? html`${renderCard({
                id: "card-device-security",
                title: "Perimeter Security",
                subtitle:
                  "Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.",
                contentClass: "settings-list",
                body: html`${renderSelectRow({
                    id: "cfg-security_pin_policy",
                    label: "Perimeter Security Policy",
                    description: html`Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy: <strong>${live.effective_security_pin_policy || curPinPolicy}</strong>.`,
                    value: curPinPolicy,
                    rawOptions: SECURITY_PIN_POLICY_OPTIONS,
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "security_pin_policy",
                        val,
                        "cfg-security_pin_policy",
                      ),
                  })}
                  ${renderSettingsRow({
                    label: "Security PIN",
                    description:
                      "Write-only 4 to 12 digit numeric PIN verified server-side (PBKDF2-HMAC-SHA256) when the on-device keypad prompts. Never echoed back to the browser.",
                    stacked: true,
                    control: html`<div class="input-action-row">
                      <span class="chip ${hasPin ? "chip-success" : ""}">
                        ${hasPin ? "PIN configured" : "Not set"}
                      </span>
                      <input
                        type="password"
                        id="dev-security-pin-input"
                        inputmode="numeric"
                        pattern="[0-9]*"
                        autocomplete="new-password"
                        aria-label="New Security PIN (4 to 12 digits)"
                        placeholder=${hasPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                        .value=${store.devicePinDraft}
                        @input=${(ev) => {
                          store.devicePinDraft = (ev.currentTarget).value;
                          store.host.requestUpdate();
                        }}
                      />
                      <button
                        type="button"
                        ?disabled=${store.pinBusy || !store.devicePinDraft.trim()}
                        @click=${() => void store.saveSecurityPin("device")}
                        class="btn btn-primary btn-compact"
                      >
                        Save PIN
                      </button>
                      ${hasPin
                        ? html`<button
                            type="button"
                            ?disabled=${store.pinBusy}
                            @click=${() => void store.clearSecurityPin("device")}
                            class="btn btn-danger btn-compact"
                          >
                            Clear PIN
                          </button>`
                        : nothing}
                    </div>`,
                  })}`,
              })}
              ${renderCard({
                id: "card-replace-hardware",
                heading: html`<h3 class="card-title">Replace Hardware</h3>`,
                contentClass: "stack",
                body: html`<p class="row-description">
                    Moving to a replacement board? Download this Device's backup first, add the new ESPHome board in Home Assistant, and restore the backup onto it from System Tools.
                  </p>
                  <div class="input-action-row">
                    <button
                      type="button"
                      @click=${() => void store.exportBackup(store.activeSubentryId)}
                      class="btn btn-secondary"
                    >
                      Download Device Backup
                    </button>
                    <button
                      type="button"
                      @click=${() => store.openSystemSection("system_tools", "card-backup-restore")}
                      class="btn btn-text"
                    >
                      Open Backup &amp; Restore
                    </button>
                  </div>`,
              })}`
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Danger Zone</h3>`,
          danger: true,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Reset to Defaults",
              description:
                "Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.",
              control: html`<button
                type="button"
                @click=${() => store.openResetDeviceModal()}
                class="btn btn-danger"
              >
                Reset to Defaults
              </button>`,
            })}
            ${renderSettingsRow({
              label: "Remove Device",
              description:
                "Removes this subentry from Latter. The ESPHome device remains in Home Assistant.",
              control: html`<button
                type="button"
                @click=${() =>
                  store.openRemoveDeviceModal(
                    store.activeSubentryId,
                    data?.title || cfg.device_slug || "Device",
                  )}
                class="btn btn-danger"
              >
                Remove Device
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/devices-list-view.ts ---
/**
 * Devices Scope Landing View (`select_device_prompt`): Filterable, keyboard-accessible sortable Devices table.
 */
function statusRank(st) {
  if (st === "Update available") return 1;
  if (st === "Offline") return 2;
  return 3;
}
function renderDevicesListView(store) {
  const allDevices = store.state?.system_devices || [];
  const groups = store.state?.device_groups || [];
  const cat = store.deviceCategoryFilter || "all";
  const baseCategories = [
    { id: "all", label: "All Devices" },
    { id: "online", label: "Online" },
    { id: "native", label: "Latter Displays" },
    { id: "ble_tracked", label: "BLE Tracked" },
    { id: "assigned_person", label: "Assigned to a Person" },
    { id: "roaming", label: "Roaming Devices" },
    { id: "stationary", label: "Stationary Devices" },
    { id: "headless", label: "Screenless Devices" },
    { id: "ble_tag", label: "BLE tags" },
    { id: "updates", label: "Firmware update available" },
  ];
  for (const g of groups) {
    if (g && g.id && g.id !== "unassigned") {
      baseCategories.push({ id: `group:${g.id}`, label: `Group: ${g.name}` });
    }
  }
  const filtered = allDevices.filter((d) => {
    const isBleTag = d.kind === "ble_tag";
    const isRoaming = isBleTag || Boolean(d.is_roaming);
    if (cat === "online") return Boolean(d.is_online);
    if (cat === "native") return Boolean(d.is_latter_native);
    if (cat === "ble_tracked") return Boolean(d.ble_tracked);
    if (cat === "assigned_person") return Boolean(d.assigned_person);
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "headless") return isBleTag || !d.has_display;
    if (cat === "ble_tag") return isBleTag;
    if (cat === "updates") return d.status_label === "Update available";
    if (cat.startsWith("group:")) return d.device_group === cat.slice(6);
    return true;
  });
  filtered.sort((a, b) => {
    let cmp = 0;
    if (store.deviceSortField === "status") {
      cmp = statusRank(a.status_label) - statusRank(b.status_label);
      if (cmp === 0) cmp = (a.title || "").localeCompare(b.title || "");
    } else if (store.deviceSortField === "model") {
      cmp = (a.model_label || "").localeCompare(b.model_label || "");
    } else if (store.deviceSortField === "area") {
      cmp = (a.area_label || "").localeCompare(b.area_label || "");
    } else if (store.deviceSortField === "group") {
      cmp = (a.device_group_name || "").localeCompare(b.device_group_name || "");
    } else {
      cmp = (a.title || "").localeCompare(b.title || "");
    }
    return store.deviceSortAsc ? cmp : -cmp;
  });
  return html`<section id="view-select_device_prompt">
    ${renderCard({
      title: "Devices",
      headerActions: html`<select
          id="device-category-filter"
          aria-label="Filter Devices by category"
          .value=${cat}
          @change=${(ev) => {
            store.deviceCategoryFilter = (ev.currentTarget).value || "all";
            store.host.requestUpdate();
          }}
        >
          ${baseCategories.map(
            (o) => html`<option value=${o.id} ?selected=${o.id === cat}>${o.label}</option>`,
          )}
        </select>
        <button
          type="button"
          @click=${() => store.openHaPage("/config/integrations/integration/latter")}
          class="btn btn-primary"
        >
          Add Device
        </button>
        <button
          type="button"
          @click=${() => store.openAddBleModal()}
          class="btn btn-secondary"
        >
          Add BLE Tag
        </button>`,
      body: filtered.length
        ? html`<div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  ${renderSortHeader(store, "title", "Device")}
                  ${renderSortHeader(store, "model", "Model")}
                  ${renderSortHeader(store, "area", "Area")}
                  ${renderSortHeader(store, "group", "Group")}
                  ${renderSortHeader(store, "status", "Status")}
                  <th><span class="sort-btn" aria-hidden="true"></span></th>
                </tr>
              </thead>
              <tbody>
                ${repeat(
                  filtered,
                  (d) => d.subentry_id,
                  (d) => {
                    const st = d.status_label || "—";
                    const dotCls =
                      st === "Update available" ? "update" : st === "Offline" ? "" : "online";
                    const openRow = () => {
                      void store.switchSystemDevice(d.subentry_id);
                    };
                    const onRowKey = (ev) => {
                      const kev = ev;
                      if (kev.key === "Enter" || kev.key === " ") {
                        kev.preventDefault();
                        openRow();
                      }
                    };
                    return html`<tr
                      tabindex="0"
                      aria-label=${`Open ${d.title}`}
                      @click=${openRow}
                      @keydown=${onRowKey}
                    >
                      <td class="col-name">${d.title}</td>
                      <td>${d.model_label || "—"}</td>
                      <td>${d.area_label || "—"}</td>
                      <td>${d.device_group_name || "—"}</td>
                      <td><span class="status-dot ${dotCls}"></span>${st}</td>
                      <td class="col-open" aria-hidden="true">›</td>
                    </tr>`;
                  },
                )}
              </tbody>
            </table>
          </div>`
        : html`<p class="empty-state">
            ${allDevices.length
              ? "No Devices match this category."
              : "No Devices yet. Latter Devices appear here after you add them in Home Assistant."}
          </p>`,
    })}
  </section>`;
}

// --- src/views/system-groups-view.ts ---
/**
 * System Device Groups View (`system_sync`, D-021): Device Groups, Baseline Seeding, Tier 2 Operational & Tier 3 Appearance Bulk Controls.
 */
function renderSystemGroupsView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];
  const activeFilter = store.groupCtrlFilter || "all";
  const activeGrpId = store.resolvedGroupCtrlId();
  const selectedGrpObj = groups.find((g) => g.id === activeGrpId) || null;
  const activeCat = store.groupCtrlCategoryFilter || "all";
  const matchingDevs = latterDevices.filter((d) => {
    if (activeGrpId === "all") return true;
    if (activeGrpId === "roaming") return Boolean(d.is_roaming);
    if (activeGrpId === "stationary") return !d.is_roaming;
    return d.device_group === activeGrpId;
  });
  const baseCfg = selectedGrpObj?.device_config || {};
  const bleOn =
    selectedGrpObj && baseCfg.native_ble_tracking !== undefined
      ? Boolean(baseCfg.native_ble_tracking)
      : matchingDevs.length
        ? matchingDevs.every((d) => d.ble_tracked)
        : false;
  const autoSw =
    selectedGrpObj && baseCfg.ble_auto_switch !== undefined
      ? Boolean(baseCfg.ble_auto_switch)
      : bleOn;
  const vfm =
    selectedGrpObj && baseCfg.sync_device_area !== undefined
      ? Boolean(baseCfg.sync_device_area)
      : false;
  const handoff =
    selectedGrpObj && baseCfg.area_handoff !== undefined
      ? Boolean(baseCfg.area_handoff)
      : false;
  const renderBulkControlRow = (fc) => {
    if (activeCat !== "all" && fc.section !== activeCat) return nothing;
    const targets = (fc.targets || []).filter((t) => {
      if (activeGrpId === "all") return true;
      if (activeGrpId === "roaming") return Boolean(t.is_roaming);
      if (activeGrpId === "stationary") return !t.is_roaming;
      return t.device_group === activeGrpId;
    });
    const rawBaselineVal = fc.pref_key
      ? selectedGrpObj?.device_config?.[fc.pref_key]
      : selectedGrpObj?.esphome_controls && fc.canonical_key
        ? selectedGrpObj.esphome_controls[fc.canonical_key]
        : undefined;
    const baselineVal =
      rawBaselineVal !== undefined && fc.domain === "switch" && typeof rawBaselineVal === "boolean"
        ? rawBaselineVal
          ? "on"
          : "off"
        : rawBaselineVal;
    if (!targets.length && baselineVal === undefined) return nothing;
    const states = targets.length
      ? Array.from(new Set(targets.map((t) => String(t.state ?? ""))))
      : baselineVal !== undefined
        ? [String(baselineVal)]
        : [];
    const mixed = states.length > 1;
    const curState = mixed ? "" : (states[0] ?? "");
    const baseNote = baselineVal !== undefined ? ` • Baseline: ${String(baselineVal)}` : "";
    const desc = `${fc.section_title} • ${targets.length} Device${targets.length === 1 ? "" : "s"}${mixed ? " • Mixed values" : ""}${baseNote}`;
    let control;
    if (fc.domain === "select" && fc.options && fc.options.length) {
      control = html`<select
        aria-label=${fc.name}
        .value=${curState}
        @change=${(ev) =>
          void store.bulkSelect(fc, (ev.currentTarget).value)}
      >
        ${mixed ? html`<option value="" selected disabled>Mixed</option>` : nothing}
        ${fc.options.map(
          (opt) => html`<option value=${opt} ?selected=${opt === curState}>${opt}</option>`,
        )}
      </select>`;
    } else if (fc.domain === "switch") {
      control = html`${mixed ? html`<span class="chip">Mixed</span>` : nothing}
        <input
          type="checkbox"
          role="switch"
          aria-label=${fc.name}
          .checked=${curState === "on"}
          @change=${(ev) =>
            void store.bulkToggle(fc, (ev.currentTarget).checked)}
          class="switch"
        />`;
    } else if (fc.domain === "number") {
      const numVal = mixed ? (fc.min ?? 0) : Number(curState) || 0;
      control = html`<input
          type="range"
          aria-label=${fc.name}
          min=${String(fc.min ?? 0)}
          max=${String(fc.max ?? 100)}
          step=${String(fc.step ?? 1)}
          .value=${String(numVal)}
          @change=${(ev) =>
            void store.bulkNumber(fc, Number((ev.currentTarget).value))}
        />
        <span class="chip">
          ${mixed ? "Mixed" : `${curState} ${fc.unit || ""}`.trim()}
        </span>`;
    } else {
      control = html`<span class="chip">${mixed ? "Mixed" : curState}</span>`;
    }
    return renderSettingsRow({ label: entityLabel(fc.name), description: desc, control });
  };
  const behaviorControls = systemControls.filter((fc) => fc.tier !== "appearance");
  const appearanceControls = systemControls.filter((fc) => fc.tier === "appearance");
  return html`<section id="view-system_sync">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Device Groups</h3>`,
          subtitle:
            "Operational baselines (sleep, wake word, BLE) shared across assigned Devices without overwriting personal appearance.",
          contentClass: "stack",
          body: html`<div class="input-action-row">
              <input
                type="text"
                id="new-group-name"
                aria-label="New Device Group name"
                placeholder="Group name (e.g. Guest Suites)"
                .value=${store.newGroupName}
                @input=${(ev) => {
                  store.newGroupName = (ev.currentTarget).value;
                }}
              />
              <input
                type="text"
                id="new-group-desc"
                aria-label="New Device Group description"
                placeholder="Optional description"
                .value=${store.newGroupDesc}
                @input=${(ev) => {
                  store.newGroupDesc = (ev.currentTarget).value;
                }}
              />
              <button
                type="button"
                @click=${() => void store.createDeviceGroup()}
                class="btn btn-primary"
              >
                Create Group
              </button>
            </div>

            <div id="device-groups-list" class="settings-list">
              ${groups.map((g) => {
                const members = allDevices.filter((d) => d.device_group === g.id);
                const isDefault = DEFAULT_DEVICE_GROUP_IDS.has(g.id) || Boolean(g.builtin);
                const customizedCnt = members.filter((m) =>
                  isGroupCustomized(m.group_sync_status),
                ).length;
                const syncMeta =
                  g.id === "unassigned" || !members.length
                    ? ""
                    : customizedCnt
                      ? `${customizedCnt} customized`
                      : "All in sync";
                const desc = [
                  g.description || "",
                  members.length ? `Devices: ${members.map((m) => m.title).join(", ")}` : "No Devices",
                  syncMeta,
                ]
                  .filter(Boolean)
                  .join(" • ");
                return renderSettingsRow({
                  labelHtml: html`<span class="row-label">
                    ${g.name} <span class="chip">${members.length}</span>
                  </span>`,
                  description: desc,
                  control: html`<button
                      type="button"
                      @click=${() => {
                        store.groupCtrlFilter = `group:${g.id}`;
                        store.host.requestUpdate();
                      }}
                      class="btn btn-text btn-compact"
                    >
                      Edit Controls
                    </button>
                    ${g.id !== "unassigned" && members.length
                      ? html`<button
                          type="button"
                          @click=${() => void store.syncDeviceGroup(g.id)}
                          class="btn btn-secondary btn-compact"
                        >
                          Sync Group
                        </button>`
                      : nothing}
                    ${!isDefault
                      ? renderTrashIconButton(`Delete group ${g.name}`, () =>
                          void store.deleteDeviceGroup(g.id),
                        )
                      : nothing}`,
                });
              })}
            </div>`,
        })}

        ${renderCard({
          title: "Seed Baseline From Device",
          subtitle: "Captures an existing Device's operational settings as a group's baseline.",
          contentClass: "stack",
          body: html`<div class="list-row-main">
              <div class="stacked-field">
                <label for="seed-group-target">Target Group</label>
                <select
                  id="seed-group-target"
                  .value=${store.seedGroupTargetId}
                  @change=${(ev) => {
                    store.seedGroupTargetId = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                >
                  ${groups
                    .filter((g) => g.id !== "unassigned")
                    .map(
                      (g) =>
                        html`<option value=${g.id} ?selected=${g.id === store.seedGroupTargetId}>
                          ${g.name}
                        </option>`,
                    )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="seed-source-device">Source Device</label>
                <select
                  id="seed-source-device"
                  .value=${store.seedSourceSubentryId}
                  @change=${(ev) => {
                    store.seedSourceSubentryId = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                >
                  ${latterDevices.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === store.seedSourceSubentryId}
                      >
                        ${d.title}
                      </option>`,
                  )}
                </select>
              </div>
            </div>
            <div class="input-action-row">
              <button
                type="button"
                @click=${() => void store.seedGroupBaselineFromDevice()}
                class="btn btn-secondary"
              >
                Save Group Baseline
              </button>
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Group Controls &amp; Baseline</h3>`,
          headerActions: html`<select
              id="group-ctrl-filter"
              aria-label="Target Devices or group"
              .value=${activeFilter}
              @change=${(ev) => {
                store.groupCtrlFilter = (ev.currentTarget).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeFilter === "all"}>All Latter Devices</option>
              <option value="trait:roaming" ?selected=${activeFilter === "trait:roaming"}>
                Roaming Devices
              </option>
              <option value="trait:stationary" ?selected=${activeFilter === "trait:stationary"}>
                Stationary Devices
              </option>
              ${groups
                .filter((g) => g.id !== "unassigned")
                .map(
                  (g) =>
                    html`<option
                      value=${`group:${g.id}`}
                      ?selected=${activeFilter === `group:${g.id}`}
                    >
                      Group: ${g.name}
                    </option>`,
                )}
            </select>
            <select
              id="group-ctrl-cat-filter"
              aria-label="Filter controls by category"
              .value=${activeCat}
              @change=${(ev) => {
                store.groupCtrlCategoryFilter =
                  (ev.currentTarget).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeCat === "all"}>All Categories</option>
              <option value="sleep" ?selected=${activeCat === "sleep"}>Sleep &amp; Wake</option>
              <option value="voice" ?selected=${activeCat === "voice"}>Voice &amp; Wake Word</option>
              <option value="sound" ?selected=${activeCat === "sound"}>Sound</option>
              <option value="area" ?selected=${activeCat === "area"}>Area &amp; BLE</option>
              <option value="display" ?selected=${activeCat === "display"}>Display</option>
              <option value="home" ?selected=${activeCat === "home"}>Home</option>
              <option value="music" ?selected=${activeCat === "music"}>Music</option>
            </select>`,
          contentClass: "stack",
          body: html`<h4 class="subsection-title">Operational Behavior (Synced with Group)</h4>
            <div id="group-latter-behavior-list" class="settings-list">
              ${activeCat === "all" || activeCat === "area"
                ? html`${renderSwitchRow({
                      label: "Track the Area with BLE Proxies",
                      description: selectedGrpObj
                        ? `Group Baseline • ${matchingDevs.length} Device(s)`
                        : `${matchingDevs.length} Device(s)`,
                      checked: bleOn,
                      onChange: (checked) =>
                        void store.setGroupDeviceSetting({ native_ble_tracking: checked }),
                    })}
                    ${renderSwitchRow({
                      label: "Auto-Switch Active Area",
                      description: "Follows BLE Area changes automatically.",
                      checked: autoSw,
                      onChange: (checked) =>
                        void store.setGroupDeviceSetting({ ble_auto_switch: checked }),
                    })}`
                : nothing}
              ${activeCat === "all" || activeCat === "voice"
                ? renderSwitchRow({
                    label: "Voice Follows Me",
                    description: "Moves roaming Devices' Home Assistant Area with them.",
                    checked: vfm,
                    onChange: (checked) =>
                      void store.setGroupDeviceSetting({ sync_device_area: checked }),
                  })
                : nothing}
              ${activeCat === "all" || activeCat === "music"
                ? renderSwitchRow({
                    label: "Media Follows Device to New Area",
                    description: "Hands off active playback when the Area changes.",
                    checked: handoff,
                    onChange: (checked) =>
                      void store.setGroupDeviceSetting({ area_handoff: checked }),
                  })
                : nothing}
            </div>

            <div id="system-controls-list" class="settings-list">
              ${behaviorControls.length
                ? behaviorControls.map((fc) => renderBulkControlRow(fc))
                : html`<p class="empty-state">No shared Device controls found.</p>`}
            </div>

            <details class="sub-collapsible">
              <summary>Appearance &amp; Personalization (Bulk Override)</summary>
              <div id="system-appearance-controls-list" class="card-content settings-list">
                ${appearanceControls.length
                  ? appearanceControls.map((fc) => renderBulkControlRow(fc))
                  : html`<p class="empty-state">No appearance controls match this filter.</p>`}
              </div>
            </details>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-overview-view.ts ---
/**
 * System Overview View (`system_overview`): Active Repairs/Issues, System Summary & Configured Items.
 */
function renderSystemOverviewView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const issues = data?.issues || [];
  const groups = data?.device_groups || [];
  const sysCfg = data?.system_config;
  const onlineCount = allDevices.filter((d) => d.is_online).length;
  const nativeCount = allDevices.filter((d) => d.is_latter_native).length;
  const bleTrackedCount = allDevices.filter((d) => d.ble_tracked).length;
  const assignedPeopleCount = allDevices.filter((d) => d.assigned_person).length;
  const verText = data?.version ? `v${String(data.version).replace(/^v/i, "")}` : "—";
  const remotesCount = (sysCfg?.remotes_list || []).length;
  const volCount = (sysCfg?.volume_overrides || []).length;
  const camerasCount = (sysCfg?.camera_entities || []).length;
  const calendarsCount = (sysCfg?.calendar_entities || []).length;
  const colorsCount = (sysCfg?.custom_palettes || []).length;
  const wallpapersCount = (data?.system_wallpapers || []).length;
  const groupsLabel = `${groups.length} group${groups.length === 1 ? "" : "s"}`;
  const makeRow = (label, value, onOpen) => html`<button
    type="button"
    @click=${onOpen}
    class="kv-row"
  >
    <span>${label}</span>
    <strong>${value}</strong>
  </button>`;
  return html`<section id="view-system_overview">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Issues",
          headerActions: html`<button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            Open Repairs
          </button>`,
          contentClass: "settings-list",
          body: issues.length
            ? issues.map((iss) => {
                const isErr = iss.severity === "error" || iss.severity === "critical";
                return renderSettingsRow({
                  labelHtml: html`<span class="row-label">
                    ${iss.device_title || "Latter"}
                    <span class="chip ${isErr ? "chip-error" : "chip-warning"}">
                      ${iss.severity === "warning" ? "Warning" : "Error"}
                    </span>
                  </span>`,
                  description: issueMessage(iss),
                  control: iss.subentry_id
                    ? html`<button
                        type="button"
                        @click=${() => void store.switchSystemDevice(String(iss.subentry_id))}
                        class="btn btn-text btn-compact"
                      >
                        Open Device
                      </button>`
                    : nothing,
                });
              })
            : html`<p class="empty-state">No issues.</p>`,
        })}

        ${renderCard({
          title: "System",
          headerActions: html`<button
            type="button"
            @click=${() => void store.checkSystemUpdates()}
            class="btn btn-secondary btn-compact"
          >
            Check Firmware Updates
          </button>`,
          body: html`<div class="kv-list">
            <div class="kv-row">
              <span>Integration Version</span>
              <strong>${verText}</strong>
            </div>
            ${makeRow(
              "Devices Online",
              `${fmtNumber(onlineCount, store.hass, 0)} / ${fmtNumber(allDevices.length, store.hass, 0)}`,
              () => store.openDevicesWithCategory("online"),
            )}
            ${makeRow("Latter Displays", fmtNumber(nativeCount, store.hass, 0), () =>
              store.openDevicesWithCategory("native"),
            )}
            ${makeRow("BLE Tracked Devices", fmtNumber(bleTrackedCount, store.hass, 0), () =>
              store.openDevicesWithCategory("ble_tracked"),
            )}
            ${makeRow("Assigned People", fmtNumber(assignedPeopleCount, store.hass, 0), () =>
              store.openDevicesWithCategory("assigned_person"),
            )}
            ${makeRow("Area BLE Proxies", fmtNumber(data?.ble_proxy_count, store.hass, 0), () =>
              store.openSystemSection("area_tracking"),
            )}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Configured Items",
          body: html`<div class="kv-list">
            ${makeRow("Device Groups", groupsLabel, () => store.openSystemSection("system_sync"))}
            ${makeRow("Cameras", fmtNumber(camerasCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-cameras-doorbell"),
            )}
            ${makeRow("Calendars", fmtNumber(calendarsCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-calendars"),
            )}
            ${makeRow("Remote Controls", fmtNumber(remotesCount, store.hass, 0), () =>
              store.openSystemSection("remotes"),
            )}
            ${makeRow("Volume Overrides", fmtNumber(volCount, store.hass, 0), () =>
              store.openSystemSection("remotes", "card-volume-overrides"),
            )}
            ${makeRow("Custom Colors", fmtNumber(colorsCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-custom-colors"),
            )}
            ${makeRow("Wallpapers", fmtNumber(wallpapersCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-system-wallpapers"),
            )}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-presence-view.ts ---
/**
 * System BLE & Area Presence View (`area_tracking`): Live Area Presence & Sensor Fusion, Streaming BLE Calibration & Discovered BLE Devices.
 */
const FUSION_MODE_OPTIONS = [
  { val: "weighted", label: "Weighted (BLE and sensors)" },
  { val: "any_or", label: "Either (BLE or a sensor)" },
  { val: "ble_only", label: "BLE only" },
  { val: "ble_and_sensor", label: "Both (BLE and a sensor)" },
];
function renderSystemPresenceView(store) {
  const data = store.state;
  const presenceRows = data?.live?.area_presence_grid || [];
  const allDevs = data?.system_devices || [];
  const bleDevs = allDevs.filter((d) => d.has_ble || d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;
  const candidates = data?.discovered_ble_devices || [];
  const persons = data?.catalog?.persons || [];
  return html`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Live Area Presence & Sensor Fusion",
          subtitle:
            "Combines Bluetooth proxy telemetry (with 6.0 dB cross-floor attenuation) and Area occupancy sensors.",
          body: html`<div id="area-presence-grid-box" class="stack">
            ${presenceRows.length
              ? repeat(
                  presenceRows,
                  (r) => r.area_id,
                  (r) => {
                    const isOcc = Boolean(r.is_occupied);
                    const occList = r.occupant_names || [];
                    const occNames = occList.length
                      ? occList.join(", ")
                      : isOcc
                        ? "Occupied (sensor)"
                        : "Empty";
                    const parts = [occNames];
                    if (r.winning_rssi !== null && r.winning_rssi !== undefined) {
                      const distPart =
                        r.closest_distance_m !== null && r.closest_distance_m !== undefined
                          ? ` (~${fmtDistance(r.closest_distance_m, store.hass, r.closest_distance_ft)})`
                          : "";
                      parts.push(`BLE ${fmtNumber(r.winning_rssi, store.hass, 0)} dBm${distPart}`);
                    }
                    if (r.active_sensors && r.active_sensors.length) {
                      parts.push(
                        `${r.active_sensors.length} active sensor${r.active_sensors.length > 1 ? "s" : ""}`,
                      );
                    } else if (r.available_sensors && r.available_sensors.length) {
                      parts.push(
                        `${r.available_sensors.length} sensor${r.available_sensors.length > 1 ? "s" : ""} clear`,
                      );
                    }
                    if (r.floor_id) parts.push(`Floor: ${r.floor_id}`);
                    const curMode = r.fusion_mode || "weighted";
                    const confPct = r.confidence_pct ?? 100;
                    const threshold = Number(r.fusion_threshold_pct ?? 50);
                    const chosen = r.fusion_sensors || [];
                    const choices = r.fusion_sensor_choices || [];
                    const thresholdId = `fusion-threshold-${r.area_id}`;
                    return html`<div class="fusion-area">
                      ${renderSettingsRow({
                        labelHtml: html`<span class="row-label">
                          ${r.area_name}
                          ${isOcc
                            ? html`<span class="chip chip-success">
                                Occupied • ${fmtPercent(confPct, store.hass)}
                              </span>`
                            : html`<span class="chip">Clear</span>`}
                        </span>`,
                        description: parts.join(" • "),
                        control: html`<select
                          aria-label=${`Fusion mode for ${r.area_name}`}
                          .value=${curMode}
                          @change=${(ev) =>
                            void store.setAreaFusion(r.area_id, {
                              mode: (ev.currentTarget).value,
                            })}
                        >
                          ${FUSION_MODE_OPTIONS.map(
                            (m) =>
                              html`<option value=${m.val} ?selected=${m.val === curMode}>
                                ${m.label}
                              </option>`,
                          )}
                        </select>`,
                      })}

                      <details
                        ?open=${store.openFusionAreas.has(r.area_id)}
                        @toggle=${(ev) => {
                          const isOpen = (ev.currentTarget).open;
                          if (isOpen) store.openFusionAreas.add(r.area_id);
                          else store.openFusionAreas.delete(r.area_id);
                        }}
                        class="sub-collapsible"
                      >
                        <summary>Fusion Settings</summary>
                        <div class="card-content settings-list">
                          ${renderSettingsRow({
                            label: "Occupied At",
                            forId: thresholdId,
                            description:
                              curMode === "weighted"
                                ? "The Area counts as occupied when the combined BLE and sensor score reaches this."
                                : "Used by the Weighted mode only.",
                            control: html`<input
                                type="range"
                                id=${thresholdId}
                                min="20"
                                max="95"
                                step="5"
                                ?disabled=${curMode !== "weighted"}
                                .value=${String(threshold)}
                                @change=${(ev) =>
                                  void store.setAreaFusion(r.area_id, {
                                    threshold_pct: Number(
                                      (ev.currentTarget).value,
                                    ),
                                  })}
                              />
                              <span class="chip">${fmtPercent(threshold, store.hass)}</span>`,
                          })}
                          ${renderSettingsRow({
                            label: "Sensors That Count",
                            description: chosen.length
                              ? `${chosen.length} of ${choices.length} selected.`
                              : "None selected: every sensor in this Area counts.",
                            stacked: true,
                            control: choices.length
                              ? html`<div
                                  role="group"
                                  aria-label=${`Sensors that count in ${r.area_name}`}
                                  class="pill-list"
                                >
                                  ${choices.map((s) => {
                                    const on = chosen.includes(s.entity_id);
                                    const nextSensors = on
                                      ? chosen.filter((x) => x !== s.entity_id)
                                      : chosen.concat([s.entity_id]);
                                    return html`<span class="pill ${on ? "enabled" : ""}">
                                      <button
                                        type="button"
                                        aria-pressed=${String(on)}
                                        title=${s.entity_id}
                                        @click=${() =>
                                          void store.setAreaFusion(r.area_id, {
                                            sensors: nextSensors,
                                          })}
                                        class="pill-toggle"
                                      >
                                        ${on ? "✓ " : ""}${s.name}
                                      </button>
                                    </span>`;
                                  })}
                                </div>`
                              : html`<p class="empty-state">
                                  This Area has no occupancy, motion or door sensors.
                                </p>`,
                          })}
                        </div>
                      </details>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Bluetooth proxies or Area occupancy sensors found yet.
                </p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Per-Area BLE Signal Calibration",
          subtitle: "Streams live RSSI deltas over WebSocket to tune per-Area offsets.",
          headerActions: html`<select
              id="ble-survey-device-picker"
              aria-label="Select Device for BLE calibration"
              .value=${activeSurveyDev?.subentry_id || ""}
              @change=${(ev) =>
                store.selectBleSurveyDevice((ev.currentTarget).value)}
            >
              ${bleDevs.length
                ? bleDevs.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === activeSurveyDev?.subentry_id}
                      >
                        ${d.title} (${d.active_area_name || "—"})
                      </option>`,
                  )
                : html`<option value="">No Bluetooth devices found</option>`}
            </select>
            <button
              type="button"
              aria-pressed=${String(store.bleLiveStreamActive)}
              @click=${() => store.toggleBleLiveStream(!store.bleLiveStreamActive)}
              class="btn ${store.bleLiveStreamActive ? "btn-primary" : "btn-secondary"} btn-compact"
            >
              ${store.bleLiveStreamActive ? "Live Stream On" : "Stream Paused"}
            </button>`,
          contentClass: "stack",
          body: html`<p class="help-text">
              Packets observed: <strong>${fmtNumber(packetsSeen, store.hass, 0)}</strong>
            </p>
            ${surveyRows.length
              ? repeat(
                  surveyRows,
                  (row) => row.area_id,
                  (row) => {
                    const pct = rssiToPercent(row.effective_rssi);
                    const sigStyle = `--signal-pct:${pct}%`;
                    const effTxt =
                      row.effective_rssi !== null && row.effective_rssi !== undefined
                        ? `${fmtNumber(row.effective_rssi, store.hass, 1)} dBm`
                        : "—";
                    const rawTxt =
                      row.raw_rssi !== null && row.raw_rssi !== undefined
                        ? `raw ${fmtNumber(row.raw_rssi, store.hass, 1)} dBm`
                        : "no signal";
                    const offVal = Number(row.offset_db || 0);
                    const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;
                    return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                      <div class="signal-row-head">
                        <span class="signal-row-title">
                          <span class="row-label">${row.area_name}</span>
                          ${row.is_winner
                            ? html`<span class="chip chip-primary">Active Winner</span>`
                            : ""}
                        </span>
                        <span class="signal-meta">${rawTxt} • offset ${offTxt} • eff ${effTxt}</span>
                      </div>
                      <div class="signal-track">
                        <div class="signal-fill" style=${sigStyle}></div>
                      </div>
                      <div class="input-action-row">
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, offVal - 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          -1 dB
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, offVal + 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          +1 dB
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, 0)}
                          class="btn btn-text btn-compact"
                        >
                          Reset
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.autoCalibrateHere(row.area_id)}
                          class="btn btn-primary btn-compact"
                        >
                          Calibrate Current Area
                        </button>
                      </div>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Area BLE proxy readings yet for this Device.
                </p>`}`,
        })}

        ${renderCard({
          title: "Discovered Bluetooth Devices",
          contentClass: "settings-list",
          body: html`<div id="ble-adopt-table-box" class="settings-list">
            ${candidates.length
              ? candidates.map((c, idx) => {
                  const title = c.title || c.name || c.target_address || c.address || "BLE Tag";
                  const addr = c.target_address || c.address || "";
                  const meta = [c.kind || "BLE device", addr];
                  if (c.rssi !== null && c.rssi !== undefined) {
                    meta.push(`${fmtNumber(c.rssi, store.hass, 0)} dBm`);
                  }
                  if (c.area_name) {
                    meta.push(`Nearest Area: ${c.area_name}`);
                  }
                  const selId = `ble-adopt-person-${idx}`;
                  return renderSettingsRow({
                    label: title,
                    description: meta.join(" • "),
                    control: html`<select id=${selId} aria-label=${`Assigned person for ${title}`}>
                        <option value="">No person</option>
                        ${persons.map((p) => html`<option value=${p.id}>${p.name}</option>`)}
                      </select>
                      <button
                        type="button"
                        @click=${(ev) => {
                          const btn = ev.currentTarget;
                          const sel = btn.parentElement?.querySelector(
                            "select",
                          );
                          void store.quickAdoptBleCandidate(title, addr, sel?.value || "");
                        }}
                        class="btn btn-secondary btn-compact"
                      >
                        Adopt
                      </button>`,
                  });
                })
              : html`<p class="empty-state">No unadopted Bluetooth devices nearby.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-remotes-view.ts ---
/**
 * System Media & Remotes View (`remotes`): Remote Controls, Volume Overrides, Remote Groups & Device Assignment Status.
 */
function renderSystemRemotesView(store) {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const remotes = sc?.remotes_list || [];
  const volOverrides = sc?.volume_overrides || [];
  const remoteGroups = sc?.remote_groups || [];
  const areas = cat.areas || [];
  const screenDevs = (data?.system_devices || []).filter(
    (d) => d.kind !== "ble_tag" && d.has_display,
  );
  const speakerChoices = cat.ma_speakers || [];
  const targetChoices = cat.volume_targets || cat.remotes || [];
  const inventoryIds = remotes.filter(Boolean);
  const friendlyRemoteLabel = (entId) => {
    const found = (cat.remotes || []).find((r) => r.id === entId);
    return found ? found.name.split(" (")[0] : entId;
  };
  const remoteAssignmentChipLabel = (rawMode) => {
    const mode = String(rawMode || "area_auto").trim() || "area_auto";
    if (mode === "all") return "All System remotes";
    if (mode.startsWith("group:")) {
      const grpId = mode.slice(6);
      const matched = remoteGroups.find((g) => g.id === grpId);
      return matched ? `Group: ${matched.name}` : `Missing group (${grpId})`;
    }
    return "Follows active Area";
  };
  return html`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Remote Controls",
          subtitle: "Up to 10 TV, streamer, or receiver entities controlled from the Remote screen.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("remotes_list", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Remote
          </button>`,
          body: renderEntitySlotList({
            id: "remotes-list",
            items: remotes,
            choices: cat.remotes,
            emptyOptionLabel: "— Choose a remote or media player —",
            emptyStateText: "No remote controls configured yet.",
            selectAriaLabel: "Remote or media player",
            removeAriaLabel: "Remove remote",
            slotLabel: (idx) => (idx === 0 ? "Slot 1 (Primary Power Target)" : `Slot ${idx + 1}`),
            onChange: (idx, val) => store.updateStringListRow("remotes_list", idx, val),
            onRemove: (idx) => store.removeStringListRow("remotes_list", idx),
          }),
        })}

        ${renderCard({
          id: "card-volume-overrides",
          title: "Speaker Volume Overrides",
          subtitle: "Redirects volume buttons when audio plays through an external AVR or soundbar.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addVolumeOverrideRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Override
          </button>`,
          body: html`<div id="volume-overrides-list" class="stack">
            ${volOverrides.length
              ? volOverrides.map(
                  (vo, idx) => html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <span class="field-label">When Audio Plays On</span>
                        <select
                          aria-label="Speaker"
                          .value=${vo.speaker}
                          @change=${(ev) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "speaker",
                              (ev.currentTarget).value,
                            )}
                        >
                          ${renderSelectOptions(speakerChoices, vo.speaker, "— Choose a speaker —")}
                        </select>
                      </div>
                      <div class="stacked-field">
                        <span class="field-label">Change the Volume On</span>
                        <select
                          aria-label="Volume target"
                          .value=${vo.target}
                          @change=${(ev) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "target",
                              (ev.currentTarget).value,
                            )}
                        >
                          ${renderSelectOptions(
                            targetChoices,
                            vo.target,
                            "— Choose a volume target —",
                          )}
                        </select>
                      </div>
                    </div>
                    ${renderTrashIconButton("Remove volume override", () =>
                      store.removeVolumeOverrideRow(idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">No volume overrides configured.</p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Remote Control Groups",
          subtitle: "Bind sets of remotes to Home Assistant Areas or specific Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addRemoteGroupRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Group
          </button>`,
          body: html`<div id="remote-groups-list" class="stack">
            ${remoteGroups.length
              ? remoteGroups.map((grp, gIdx) => {
                  const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
                  const pool = selectedRems
                    .filter((id) => inventoryIds.includes(id))
                    .concat(inventoryIds.filter((id) => !selectedRems.includes(id)));
                  return html`<div class="list-block">
                    <div class="list-row-head">
                      <div class="list-row-main">
                        <div class="stacked-field">
                          <label>Group Name</label>
                          <input
                            type="text"
                            aria-label="Group name"
                            placeholder="e.g. Living Area TV"
                            .value=${grp.name || ""}
                            @change=${(ev) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "name",
                                (ev.currentTarget).value,
                              )}
                          />
                        </div>
                        <div class="stacked-field">
                          <label>Loads in Area</label>
                          <select
                            aria-label="Area"
                            .value=${grp.area_id || ""}
                            @change=${(ev) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "area_id",
                                (ev.currentTarget).value,
                              )}
                          >
                            <option value="">No Area (assign to Devices only)</option>
                            ${areas.map(
                              (a) =>
                                html`<option value=${a.id} ?selected=${a.id === grp.area_id}>
                                  ${a.name}
                                </option>`,
                            )}
                          </select>
                        </div>
                      </div>
                      ${renderTrashIconButton(`Delete remote group ${grp.name || ""}`, () =>
                        store.removeRemoteGroupRow(grp.id),
                      )}
                    </div>
                    <div class="stacked-field">
                      <span id=${`rg-remotes-${gIdx}`} class="field-label">Remote Controls</span>
                      <div role="group" aria-labelledby=${`rg-remotes-${gIdx}`} class="pill-list">
                        ${pool.length
                          ? pool.map((entId) => {
                              const pos = selectedRems.indexOf(entId);
                              const isEn = pos >= 0;
                              const badge = isEn
                                ? pos === 0
                                  ? "★ Primary: "
                                  : `#${pos + 1}: `
                                : "+ ";
                              return html`<button
                                type="button"
                                aria-pressed=${String(isEn)}
                                @click=${() => store.toggleRemoteInGroup(grp.id, entId)}
                                class="pill ${isEn ? "enabled" : ""}"
                              >
                                ${badge}${friendlyRemoteLabel(entId)}
                              </button>`;
                            })
                          : html`<span class="help-text">Add remote controls first.</span>`}
                      </div>
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No remote groups yet.</p>`}
          </div>`,
        })}

        ${renderCard({
          title: "Device Assignments",
          subtitle: "Assigned on each Device's Interface page.",
          contentClass: "settings-list",
          body: html`<div id="device-remote-assignments-list" class="settings-list">
            ${screenDevs.length
              ? screenDevs.map((d) =>
                  renderSettingsRow({
                    label: d.title,
                    description: `Active Area: ${d.active_area_name || "—"}`,
                    control: html`<span class="chip">${remoteAssignmentChipLabel(d.device_remote_group)}</span>
                      <button
                        type="button"
                        aria-label=${`Configure remotes for ${d.title}`}
                        @click=${() => void store.switchSystemDevice(d.subentry_id, "interface")}
                        class="btn btn-secondary btn-compact"
                      >
                        Configure
                      </button>`,
                  }),
                )
              : html`<p class="empty-state">No Devices with a screen yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-shared-view.ts ---
/**
 * System Shared Entities View (`shared_entities`): Whole-Home Entities, Calendars, Cameras & Doorbell Audio, Custom Colors & Wallpapers (D-022).
 */
const TALK_STATE_TEXT = {
  listening: "listening",
  talking: "replying",
};
const DOORBELL_FILTER_OPTIONS = [
  { value: "strong", label: "Strong" },
  { value: "light", label: "Light" },
  { value: "off", label: "Off" },
];
function renderSystemSharedView(store) {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const cameras = sc?.camera_entities || [];
  const calendars = sc?.calendar_entities || [];
  const palettes = sc?.custom_palettes || [];
  const doorbells = data?.doorbells || [];
  const wallpapers = data?.system_wallpapers || [];
  const displayDevs = (data?.system_devices || []).filter((d) => d.kind !== "ble_tag");
  const noiseRed = sc?.doorbell_noise_reduction || "strong";
  const wholeHomeFields
     = [
    { key: "weather_entity", label: "Weather", choices: cat.weathers },
    { key: "alarm_entity", label: "Alarm Control Panel", choices: cat.alarms },
    { key: "thermostat_entity", label: "Primary Thermostat", choices: cat.climates },
    { key: "lock_entity", label: "Primary Door Lock", choices: cat.locks },
    { key: "garage_entity", label: "Garage or Gate Cover", choices: cat.garages },
    { key: "vacuum_entity", label: "Robot Vacuum", choices: cat.vacuums },
  ];
  return html`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Whole-Home Entities</h3>`,
          subtitle: "Shared entities shown across Home Hub, Weather, and Area views on every Device.",
          contentClass: "settings-list",
          body: wholeHomeFields.map((f) =>
            renderSelectRow({
              id: `cfg-${f.key}`,
              label: f.label,
              value: sc?.[f.key],
              choices: f.choices,
              emptyOptionLabel: "— None —",
              onChange: (val) => store.stageSystemSetting(f.key, val, `cfg-${f.key}`),
            }),
          ),
        })}

        ${renderCard({
          id: "card-calendars",
          heading: html`<h3 class="card-title">Calendars</h3>`,
          subtitle: "Upcoming events merged into the Activity Card and agenda feed.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("calendar_entities", "", 50)}
            class="btn btn-secondary btn-compact"
          >
            Add Calendar
          </button>`,
          body: renderEntitySlotList({
            id: "calendars-list",
            items: calendars,
            choices: cat.calendars,
            emptyOptionLabel: "— Choose a calendar —",
            emptyStateText: "No calendars configured yet.",
            selectAriaLabel: "Calendar",
            removeAriaLabel: "Remove calendar",
            onChange: (idx, val) => store.updateStringListRow("calendar_entities", idx, val),
            onRemove: (idx) => store.removeStringListRow("calendar_entities", idx),
          }),
        })}

        ${renderCard({
          id: "card-system-wallpapers",
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared System wallpapers and presets available to every Latter display.",
          headerActions: renderWallpaperUploadTrigger(store, "system"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "system")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(store, "system", wallpapers, "square")}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-cameras-doorbell",
          heading: html`<h3 class="card-title">Cameras &amp; Doorbell Audio</h3>`,
          subtitle:
            "Up to 10 cameras. Doorbell ring sensors wake displays automatically with listen audio and push-to-talk TTS replies.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("camera_entities", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Camera
          </button>`,
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${renderSelectRow({
                id: "cfg-doorbell_noise_reduction",
                label: "Doorbell Audio Filter",
                description:
                  "FFmpeg noise-reduction preset applied when listening to camera audio.",
                value: noiseRed,
                rawOptions: DOORBELL_FILTER_OPTIONS,
                onChange: (val) =>
                  store.stageSystemSetting(
                    "doorbell_noise_reduction",
                    val,
                    "cfg-doorbell_noise_reduction",
                  ),
              })}
              ${displayDevs.length && cameras.length
                ? renderSettingsRow({
                    label: "Test Door Speaker Reply",
                    description: "Plays a short TTS phrase on Camera 1's bound media player.",
                    control: html`<select
                        aria-label="Source Device for door speaker test"
                        .value=${store.doorbellTestSubentryId}
                        @change=${(ev) => {
                          store.doorbellTestSubentryId = (
                            ev.currentTarget
                          ).value;
                          store.host.requestUpdate();
                        }}
                      >
                        ${displayDevs.map(
                          (d) =>
                            html`<option
                              value=${d.subentry_id}
                              ?selected=${d.subentry_id === store.doorbellTestSubentryId}
                            >
                              ${d.title}
                            </option>`,
                        )}
                      </select>
                      <button
                        type="button"
                        @click=${() => void store.testDoorbellSpeaker()}
                        class="btn btn-secondary btn-compact"
                      >
                        Test Speaker
                      </button>`,
                  })
                : nothing}
            </div>

            ${renderEntitySlotList({
              id: "cameras-list",
              items: cameras,
              choices: cat.cameras,
              emptyOptionLabel: "— Choose a camera —",
              emptyStateText: "No cameras configured yet.",
              selectAriaLabel: "Camera",
              removeAriaLabel: "Remove camera",
              slotLabel: (idx) => (idx === 0 ? "Camera 1 (Primary)" : `Camera ${idx + 1}`),
              extraActions: (camId) => html`<button
                type="button"
                ?disabled=${!camId}
                @click=${() => void store.previewCamera(camId)}
                class="btn btn-text btn-compact"
              >
                Preview
              </button>`,
              onChange: (idx, val) => store.updateStringListRow("camera_entities", idx, val),
              onRemove: (idx) => store.removeStringListRow("camera_entities", idx),
            })}

            ${store.cameraPreviewUrl
              ? html`<div id="cam-preview-box" class="cam-preview">
                  <div class="input-action-row">
                    <span class="field-label">Preview: ${store.activeCameraPreviewEntity}</span>
                    <button
                      type="button"
                      @click=${() => void store.previewCamera(store.activeCameraPreviewEntity, true)}
                      class="btn btn-secondary btn-compact"
                    >
                      Refresh
                    </button>
                    <button
                      type="button"
                      @click=${() => store.closeCameraPreview()}
                      class="btn btn-text btn-compact"
                    >
                      Close
                    </button>
                  </div>
                  <img
                    id="cam-preview-img"
                    src=${store.cameraPreviewUrl}
                    alt="Camera preview"
                  />
                </div>`
              : nothing}

            ${doorbells.length
              ? html`<div id="doorbell-status" class="stack">
                  <h4 class="subsection-title">Doorbells</h4>
                  <div id="doorbell-status-list" class="kv-list">
                    ${doorbells.map((b) => {
                      let ring = "No ring sensor found";
                      const ringEnt = b.ring_entity || "";
                      if (ringEnt) {
                        const when = b.ring_at
                          ? fmtAgo((Date.now() - Date.parse(b.ring_at)) / 1000, store.hass)
                          : "";
                        const st = ringEnt.startsWith("event.")
                          ? when
                            ? `last ring ${when}`
                            : "no ring yet"
                          : b.ring_state === "on"
                            ? "ringing"
                            : b.ring_state
                              ? `idle${when ? `, changed ${when}` : ""}`
                              : "unavailable";
                        ring = `${b.ring_name || ringEnt}: ${st}`;
                      }
                      const talk = (b.talk || [])
                        .map((t) => `${t.device_title} ${TALK_STATE_TEXT[t.state] || t.state}`)
                        .join(", ");
                      return html`<div class="kv-row">
                        <span>${entityLabel(b.camera_name || b.camera_entity)}</span>
                        <strong>${ring}${talk ? ` • ${talk}` : ""}</strong>
                      </div>`;
                    })}
                  </div>
                </div>`
              : nothing}`,
        })}

        ${renderCard({
          id: "card-custom-colors",
          heading: html`<h3 class="card-title">Custom Colors</h3>`,
          subtitle: "Shared 24-swatch accent library available across all Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.openColorWheelModal("system")}
            class="btn btn-secondary btn-compact"
          >
            Add Color
          </button>`,
          contentClass: "settings-list",
          body: html`<div id="sys-custom-palettes-list" class="settings-list">
            ${palettes.length
              ? palettes.map((p) => {
                  const h = p.hex.toUpperCase();
                  const swStyle = `--swatch-color:${h}`;
                  return renderSettingsRow({
                    labelHtml: html`<span class="row-label">
                      <span class="swatch" style=${swStyle} aria-hidden="true"></span>
                      ${p.name || h}
                    </span>`,
                    description: html`<code>${h}</code>`,
                    control: renderTrashIconButton(`Delete color ${p.name || h}`, () =>
                      store.deleteCustomPalette(h),
                    ),
                  });
                })
              : html`<p class="empty-state">No custom colors saved yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-tools-view.ts ---
/**
 * System Tools View (`system_tools`): Notifications & Announcements, Backup & Restore, Perimeter Security & Signing, and Logs-only `system_log`.
 */
function renderSystemToolsView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const hasSystemPin = Boolean(data?.has_security_pin);
  const isBroadcast = store.announceMode === "broadcast";
  const onAnnounceRadioKey = (ev) => {
    const kev = ev;
    if (kev.key !== "ArrowLeft" && kev.key !== "ArrowRight") return;
    kev.preventDefault();
    const nextMode = store.announceMode === "notify" ? "broadcast" : "notify";
    store.announceMode = nextMode;
    store.host.requestUpdate();
    const group = (kev.currentTarget).parentElement;
    const nextBtn = group?.querySelector(
      `[data-mode="${nextMode}"]`,
    );
    nextBtn?.focus();
  };
  return html`<section id="view-system_tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Notifications &amp; Announcements</h3>`,
          subtitle:
            "Send screen popups or spoken intercom broadcasts to all Devices, Occupied Areas, or one display.",
          contentClass: "stack",
          body: html`<div role="radiogroup" aria-label="Announcement mode" class="segmented">
              <button
                type="button"
                data-mode="notify"
                tabindex=${!isBroadcast ? "0" : "-1"}
                aria-checked=${!isBroadcast}
                @click=${() => {
                  store.announceMode = "notify";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Screen Notification
              </button>
              <button
                type="button"
                data-mode="broadcast"
                tabindex=${isBroadcast ? "0" : "-1"}
                aria-checked=${isBroadcast}
                @click=${() => {
                  store.announceMode = "broadcast";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Voice Broadcast
              </button>
            </div>

            <div class="stacked-field">
              <label for="ann-target">Target</label>
              <select
                id="ann-target"
                .value=${store.announceTarget}
                @change=${(ev) => {
                  store.announceTarget = (ev.currentTarget).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.announceTarget === "all"}>
                  All Latter Displays
                </option>
                <option
                  value="occupied_areas"
                  ?selected=${store.announceTarget === "occupied_areas"}
                >
                  Occupied Areas Only
                </option>
                ${latterDevices.map(
                  (d) =>
                    html`<option
                      value=${d.device_slug}
                      ?selected=${store.announceTarget === d.device_slug}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            ${!isBroadcast
              ? html`<div class="stacked-field">
                    <label for="ann-title">Notification Title</label>
                    <input
                      type="text"
                      id="ann-title"
                      placeholder="e.g. Front Gate"
                      .value=${store.announceTitle}
                      @input=${(ev) => {
                        store.announceTitle = (ev.currentTarget).value;
                      }}
                    />
                  </div>
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="ann-priority">Priority</label>
                      <select
                        id="ann-priority"
                        .value=${store.announcePriority}
                        @change=${(ev) => {
                          store.announcePriority = (ev.currentTarget).value
                                        ;
                        }}
                      >
                        <option value="normal">Normal</option>
                        <option value="warning">Warning</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                    <label class="inline-switch">
                      <input
                        type="checkbox"
                        role="switch"
                        .checked=${store.announceIncludeCamera}
                        @change=${(ev) => {
                          store.announceIncludeCamera = (
                            ev.currentTarget
                          ).checked;
                        }}
                        class="switch"
                      />
                      <span>Include Primary Camera</span>
                    </label>
                  </div>`
              : nothing}

            <div class="stacked-field">
              <label for="ann-message">Message</label>
              <textarea
                id="ann-message"
                rows="3"
                placeholder="Message to display or speak…"
                .value=${store.announceMessage}
                @input=${(ev) => {
                  store.announceMessage = (ev.currentTarget).value;
                }}
              ></textarea>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                @click=${() => void store.sendAnnouncement()}
                class="btn btn-primary"
              >
                Send Now
              </button>
            </div>`,
        })}

        <details
          ?open=${store.logsOpen}
          @toggle=${(ev) =>
            store.onToggleLogsDetails((ev.currentTarget).open)}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">System &amp; Device Logs</h3>
            </div>
          </summary>
          <div class="card-content stack">
            <div class="input-action-row">
              <select
                aria-label="Filter diagnostic logs"
                .value=${store.logFilter}
                @change=${(ev) => {
                  store.logFilter = (ev.currentTarget).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.logFilter === "all"}>All Events</option>
                <option value="latter" ?selected=${store.logFilter === "latter"}>Latter Studio</option>
                <option value="errors" ?selected=${store.logFilter === "errors"}>
                  Warnings &amp; Errors
                </option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${`device:${d.device_slug}`}
                      ?selected=${store.logFilter === `device:${d.device_slug}`}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
              <button
                type="button"
                @click=${() => void store.refreshState({ includeLogs: true })}
                class="btn btn-secondary btn-compact"
              >
                Refresh Logs
              </button>
              <button
                type="button"
                @click=${() => void store.copyLogsToClipboard()}
                class="btn btn-secondary btn-compact"
              >
                Copy Logs
              </button>
              <button
                type="button"
                @click=${() => void store.clearInternalLogs()}
                class="btn btn-text btn-compact"
              >
                Clear Studio Events
              </button>
              <button
                type="button"
                @click=${() => store.openHaPage("/config/logs")}
                class="btn btn-text btn-compact"
              >
                Open Native HA Logs
              </button>
            </div>
            <pre class="log-output">${store.formatVisibleLogs()}</pre>
          </div>
        </details>
      </div>

      <div class="column">
        ${renderCard({
          id: "card-backup-restore",
          heading: html`<h3 class="card-title">Backup &amp; Restore</h3>`,
          subtitle:
            "Export or restore non-secret System and Device configurations as portable JSON bundles.",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="bkp-scope-select">Export Scope</label>
              <div class="input-action-row">
                <select
                  id="bkp-scope-select"
                  .value=${store.backupExportScope}
                  @change=${(ev) => {
                    store.backupExportScope = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                >
                  <option value="system" ?selected=${store.backupExportScope === "system"}>
                    Entire System + All Devices
                  </option>
                  ${allDevices.map(
                    (d) =>
                      html`<option
                        value=${`device:${d.subentry_id}`}
                        ?selected=${store.backupExportScope === `device:${d.subentry_id}`}
                      >
                        Device: ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() => void store.exportBackup()}
                  class="btn btn-secondary"
                >
                  Download Backup
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="bkp-upload-file">Restore From Backup</label>
              <input
                type="file"
                id="bkp-upload-file"
                accept=".json,application/json"
                @change=${(ev) => {
                  const inp = ev.currentTarget;
                  store.selectedBackupFile = inp.files && inp.files[0] ? inp.files[0] : null;
                  store.host.requestUpdate();
                }}
              />
            </div>

            <div class="stacked-field">
              <label for="bkp-restore-device">Target Device (for Single-Device Backups)</label>
              <select
                id="bkp-restore-device"
                .value=${store.backupRestoreSubentryId}
                @change=${(ev) => {
                  store.backupRestoreSubentryId = (ev.currentTarget).value;
                  store.host.requestUpdate();
                }}
              >
                <option value="">— Automatic (System Backup) —</option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${d.subentry_id}
                      ?selected=${d.subentry_id === store.backupRestoreSubentryId}
                    >
                      ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            <label class="inline-switch">
              <input
                type="checkbox"
                id="bkp-restore-esp"
                role="switch"
                .checked=${store.backupRestoreEsp}
                @change=${(ev) => {
                  store.backupRestoreEsp = (ev.currentTarget).checked;
                }}
                class="switch"
              />
              <span>Restore On-Device ESPHome Controls</span>
            </label>

            <div class="input-action-row">
              <button
                type="button"
                ?disabled=${!store.selectedBackupFile}
                @click=${() => void store.restoreFromUploadedFile()}
                class="btn btn-primary"
              >
                Restore Backup
              </button>
            </div>`,
        })}

        ${renderCard({
          title: "Perimeter Security & Signing",
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "System Security PIN",
              description:
                "Default numeric PIN (4 to 12 digits, PBKDF2-HMAC-SHA256) used when a Device's Perimeter Security Policy requires PIN verification.",
              stacked: true,
              control: html`<div class="input-action-row">
                <span id="sys-security-pin-status" class="chip ${hasSystemPin ? "chip-success" : ""}">
                  ${hasSystemPin ? "PIN configured" : "Not set"}
                </span>
                <input
                  type="password"
                  id="sys-security-pin-input"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="new-password"
                  aria-label="System Security PIN (4 to 12 digits)"
                  placeholder=${hasSystemPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                  .value=${store.systemPinDraft}
                  @input=${(ev) => {
                    store.systemPinDraft = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                />
                <button
                  type="button"
                  ?disabled=${store.pinBusy || !store.systemPinDraft.trim()}
                  @click=${() => void store.saveSecurityPin("system")}
                  class="btn btn-primary btn-compact"
                >
                  Save PIN
                </button>
                ${hasSystemPin
                  ? html`<button
                      type="button"
                      id="btn-clear-security-pin"
                      ?disabled=${store.pinBusy}
                      @click=${() => void store.clearSecurityPin("system")}
                      class="btn btn-danger btn-compact"
                    >
                      Clear PIN
                    </button>`
                  : nothing}
              </div>`,
            })}
            ${renderSettingsRow({
              label: "HTTP Resource Signing Key",
              description:
                "Rotates the System HMAC secret and pushes refreshed signed artwork, map, camera, and wallpaper URLs to online Devices.",
              control: html`<button
                type="button"
                @click=${() => void store.rotateSigningKey()}
                class="btn btn-secondary btn-compact"
              >
                Rotate Signing Key
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/index.ts ---
/**
 * Active-View-Only Router (`D-023`, `D-026`): Renders ONLY the currently active Studio view.
 */
function renderActiveView(store) {
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
    case "display":
      return renderDeviceDisplayView(store);
    case "interface":
      return renderDeviceInterfaceView(store);
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

// --- src/latter-studio.ts ---
/**
 * `<latter-studio>` Custom Element — Modular TypeScript + Lit Architecture (`D-023`).
 *
 * - Zero global `window` property bindings; state is owned per element by `StudioStore`.
 * - Active-view-only rendering via `renderActiveView(this.store)`.
 * - Full WAI-ARIA `tablist` / roving arrow-key focus on Scope tabs and `aria-current="page"` on sidebar nav.
 * - Dedicated reload banner when `studio_rev_mismatch` is signaled after an HACS update.
 */
const SYSTEM_NAV_ITEMS = [
  { viewId: "system_overview", label: "Overview" },
  { viewId: "shared_entities", label: "Shared Entities" },
  { viewId: "remotes", label: "Media & Remotes" },
  { viewId: "system_sync", label: "Device Groups" },
  { viewId: "area_tracking", label: "BLE & Area Presence" },
  { viewId: "system_tools", label: "Tools" },
];
class LatterStudio extends LitElement {
  static styles = STUDIO_STYLES;
           store;
          _narrow = false;
          _route = null;
          _panel = null;
          _routeInitialized = false;
  constructor() {
    super();
    this.store = new StudioStore(this);
    this.addController(this.store);
  }
           connectedCallback() {
    super.connectedCallback();
    if (!this._routeInitialized) {
      this._routeInitialized = true;
      this._applyRoute();
    }
  }
  set hass(h) {
    this.toggleAttribute("dark", Boolean(h?.themes?.darkMode ?? h?.selectedTheme?.dark));
    this.store.setHass(h);
  }
  get hass() {
    return this.store.hass;
  }
  set narrow(n) {
    const next = Boolean(n);
    if (this._narrow === next) return;
    this._narrow = next;
    this.toggleAttribute("narrow", next);
    this.requestUpdate();
  }
  get narrow() {
    return this._narrow;
  }
  set panel(p) {
    this._panel = p;
  }
  get panel() {
    return this._panel;
  }
  set route(r) {
    const prevPath = this._route?.path ?? null;
    this._route = r;
    if (this._routeInitialized && r && r.path !== prevPath) {
      this._applyRoute();
    }
  }
  get route() {
    return this._route;
  }
          _applyRoute() {
    this.store.applyRoute(this._route);
  }
          _onScopeTabKeyDown(ev) {
    if (
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight" &&
      ev.key !== "Home" &&
      ev.key !== "End"
    ) {
      return;
    }
    ev.preventDefault();
    const currentIsDevice = this.store.currentScope === "device";
    let nextScope;
    if (ev.key === "Home") {
      nextScope = "device";
    } else if (ev.key === "End") {
      nextScope = "system";
    } else {
      nextScope = currentIsDevice ? "system" : "device";
    }
    if (nextScope === "device") {
      this.store.openDevicesLanding();
      const btn = this.renderRoot.querySelector("#tab-scope-device");
      btn?.focus();
    } else {
      this.store.setScope("system");
      const btn = this.renderRoot.querySelector("#tab-scope-system");
      btn?.focus();
    }
  }
                     updated() {
    syncStudioDialogs(this.renderRoot, this.store);
  }
          _renderDeviceNav() {
    const data = this.store.state;
    const caps = data?.capabilities || {};
    const isBleOnly = data?.config?.kind === "ble_tag";
    const items = [
      { viewId: "dashboard", label: "Overview" },
    ];
    if (!isBleOnly && caps.has_display !== false) {
      items.push({ viewId: "display", label: "Display", id: "nav-btn-display" });
      items.push({ viewId: "interface", label: "Interface", id: "nav-btn-interface" });
    }
    if (!isBleOnly && (caps.has_audio !== false || caps.has_voice !== false)) {
      items.push({ viewId: "audio_voice", label: "Audio", id: "nav-btn-audio_voice" });
    }
    if (!isBleOnly && caps.has_power) {
      items.push({ viewId: "power", label: "Power", id: "nav-btn-power" });
    }
    items.push({ viewId: "presence", label: "Presence" });
    items.push({ viewId: "tools", label: "Tools" });
    return html`<nav id="nav-scope-device" aria-label="Device pages" class="nav-list">
      <button
        type="button"
        @click=${() => this.store.openDevicesLanding()}
        class="nav-btn nav-back-btn"
      >
        <span>&larr; All Devices</span>
      </button>
      <div id="nav-selected-device-label" class="nav-device-title">
        ${data?.title || "—"}
      </div>
      ${items.map((item) => {
        const active = this.store.currentViewId === item.viewId;
        return html`<button
          type="button"
          id=${item.id || nothing}
          data-view=${item.viewId}
          aria-current=${active ? "page" : nothing}
          @click=${() => this.store.switchView(item.viewId)}
          class="nav-btn ${active ? "active" : ""}"
        >
          <span>${item.label}</span>
        </button>`;
      })}
    </nav>`;
  }
          _renderSidebar() {
    const isDeviceScope = this.store.currentScope === "device";
    const deviceCount = (this.store.state?.system_devices || []).length;
    const allDevicesActive = isDeviceScope && (!this.store.deviceSelected || this.store.currentViewId === "select_device_prompt");
    return html`<aside class="sidebar">
      <div role="tablist" aria-label="Scope" class="scope-tabs">
        <button
          type="button"
          id="tab-scope-device"
          role="tab"
          aria-selected=${isDeviceScope ? "true" : "false"}
          tabindex=${isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.openDevicesLanding()}
          @keydown=${(ev) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${isDeviceScope ? "active" : ""}"
        >
          Devices
        </button>
        <button
          type="button"
          id="tab-scope-system"
          role="tab"
          aria-selected=${!isDeviceScope ? "true" : "false"}
          tabindex=${!isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.setScope("system")}
          @keydown=${(ev) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${!isDeviceScope ? "active" : ""}"
        >
          System
        </button>
      </div>

      ${!isDeviceScope
        ? html`<nav id="nav-scope-system" aria-label="System pages" class="nav-list">
            ${SYSTEM_NAV_ITEMS.map((item) => {
              const active = this.store.currentViewId === item.viewId;
              return html`<button
                type="button"
                data-view=${item.viewId}
                aria-current=${active ? "page" : nothing}
                @click=${() => this.store.switchView(item.viewId)}
                class="nav-btn ${active ? "active" : ""}"
              >
                <span>${item.label}</span>
              </button>`;
            })}
          </nav>`
        : this.store.deviceSelected && this.store.currentViewId !== "select_device_prompt"
          ? this._renderDeviceNav()
          : html`<nav id="nav-scope-devices-list" aria-label="Devices" class="nav-list">
              <button
                type="button"
                data-view="select_device_prompt"
                aria-current=${allDevicesActive ? "page" : nothing}
                @click=${() => this.store.openDevicesLanding()}
                class="nav-btn ${allDevicesActive ? "active" : ""}"
              >
                <span>All Devices</span>
                <span id="nav-system-count" class="nav-badge">${this.store.state ? String(deviceCount) : "—"}</span>
              </button>
            </nav>`}
    </aside>`;
  }
                     render() {
    const data = this.store.state;
    const isInitialLoading = this.store.loading && !data && !this.store.loadError && !this.store.studioRevMismatch;
    const showHeaderUpdate =
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      Boolean(data?.live?.fw_update_available && data?.live?.fw_update_entity);
    const subtitle = this.store.pageSubtitle;
    return html`<div
      id="studio-root"
      class="studio-root ${isInitialLoading ? "is-loading" : ""}"
    >
      ${this.store.studioRevMismatch
        ? html`<div role="status" class="studio-rev-banner">
            <span>Latter Studio was updated — Reload Page</span>
            <button
              type="button"
              @click=${() => this.store.reloadPage()}
              class="btn btn-primary btn-compact"
            >
              Reload Page
            </button>
          </div>`
        : nothing}

      <header class="latter-top-titlebar">
        <div class="titlebar-brand">
          <button
            type="button"
            aria-label="Toggle the Home Assistant sidebar"
            @click=${() => this.store.toggleParentHaSidebar()}
            class="btn-icon ha-menu-btn"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z" />
            </svg>
          </button>
          <span class="titlebar-title">Latter</span>
        </div>
        <div class="titlebar-actions">
          ${showHeaderUpdate
            ? html`<button
                type="button"
                id="hdr-update-pill"
                @click=${() => void this.store.triggerHeaderFirmwareUpdate()}
                class="btn btn-secondary btn-compact"
              >
                Install Update
              </button>`
            : nothing}
        </div>
      </header>

      <div class="app-shell">
        ${this._renderSidebar()}

        <main
          class="main-area"
          @focusout=${() => void this.store.flushAllPendingSettings()}
        >
          <div class="content-wrap">
            <h2 id="unified-page-title" class="page-title">
              <span>${this.store.pageTitle}</span>
              ${subtitle ? html`<span class="page-subtitle">${subtitle}</span>` : nothing}
            </h2>

            ${isInitialLoading
              ? html`<div id="studio-loading" role="status" class="loading-state">
                  Loading Latter…
                </div>`
              : nothing}

            ${!data && this.store.loadError
              ? html`<div id="studio-load-error" role="alert" class="alert alert-error">
                  <span id="studio-load-error-text">${this.store.loadError}</span>
                  <button
                    type="button"
                    @click=${() => void this.store.refreshState()}
                    class="btn btn-secondary btn-compact"
                  >
                    Retry
                  </button>
                </div>`
              : nothing}

            ${data ? renderActiveView(this.store) : nothing}
          </div>
        </main>
      </div>

      ${renderStudioDialogs(this.store)}

      ${this.store.toastMessage
        ? html`<div
            role="status"
            aria-live="polite"
            class="toast ${this.store.toastIsError ? "error" : ""}"
          >
            ${this.store.toastMessage}
          </div>`
        : nothing}
    </div>`;
  }
}
if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
