/**
 * Lightweight, strictly typed Lit reactive element & `<template>` marker-part engine for Latter Studio.
 * Preserves live DOM nodes (focus, cursor selection, open selects/details/dialogs) across reactive updates.
 */

export const nothing: symbol = Symbol.for("latter.lit.nothing");

export interface CSSResult {
  readonly styleSheetText: string;
}

export function css(strings: TemplateStringsArray, ...values: unknown[]): CSSResult {
  let out = "";
  for (let i = 0; i < strings.length; i += 1) {
    out += strings[i];
    if (i < values.length) {
      const v = values[i];
      if (v && typeof v === "object" && "styleSheetText" in (v as CSSResult)) {
        out += (v as CSSResult).styleSheetText;
      } else if (v !== undefined && v !== null) {
        out += String(v);
      }
    }
  }
  return { styleSheetText: out };
}

export interface ReactiveController {
  hostConnected?(): void;
  hostDisconnected?(): void;
  hostUpdate?(): void;
  hostUpdated?(): void;
}

export interface ReactiveControllerHost {
  addController(controller: ReactiveController): void;
  removeController(controller: ReactiveController): void;
  requestUpdate(): void;
  readonly updateComplete: Promise<boolean>;
}

export interface TemplateResult {
  readonly _$litType$: 1;
  readonly strings: TemplateStringsArray;
  readonly values: readonly unknown[];
}

export interface KeyedResult {
  readonly _$litKeyed$: 1;
  readonly keys: readonly unknown[];
  readonly templates: readonly TemplateResult[];
}

export function html(strings: TemplateStringsArray, ...values: unknown[]): TemplateResult {
  return { _$litType$: 1, strings, values };
}

export function repeat<T>(
  items: readonly T[],
  keyFn: (item: T, index: number) => unknown,
  templateFn: (item: T, index: number) => TemplateResult,
): KeyedResult {
  const keys: unknown[] = [];
  const templates: TemplateResult[] = [];
  for (let i = 0; i < items.length; i += 1) {
    keys.push(keyFn(items[i], i));
    templates.push(templateFn(items[i], i));
  }
  return { _$litKeyed$: 1, keys, templates };
}

type BindingDescriptor =
  | { kind: "event"; markerAttr: string; eventName: string; partIndex: number }
  | { kind: "prop"; markerAttr: string; propName: string; partIndex: number }
  | { kind: "bool"; markerAttr: string; attrName: string; partIndex: number }
  | { kind: "attr"; markerAttr: string; attrName: string; statics: string[]; partIndices: number[] }
  | { kind: "child"; commentText: string; partIndex: number };

interface CompiledTemplate {
  templateEl: HTMLTemplateElement;
  descriptors: BindingDescriptor[];
}

const TEMPLATE_CACHE = new WeakMap<TemplateStringsArray, CompiledTemplate>();

function compileTemplate(strings: TemplateStringsArray): CompiledTemplate {
  const cached = TEMPLATE_CACHE.get(strings);
  if (cached) return cached;

  const descriptors: BindingDescriptor[] = [];
  let markup = "";
  let inTag = false;
  let quoteChar = "";
  let pendingAttrStart = -1;
  let pendingAttrPrefix = "";
  let pendingAttrName = "";
  let pendingAttrStatics: string[] = [];
  let pendingAttrParts: number[] = [];
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
  const compiled: CompiledTemplate = { templateEl, descriptors };
  TEMPLATE_CACHE.set(strings, compiled);
  return compiled;
}

interface LivePart {
  readonly priority: number;
  update(values: readonly unknown[]): void;
}

class EventPart implements LivePart {
  readonly priority = 1;
  private handler: ((ev: Event) => void) | null = null;
  private bound = false;
  private readonly wrapper = (ev: Event): void => {
    if (typeof this.handler === "function") {
      this.handler(ev);
    }
  };

  private readonly el: Element;
  private readonly eventName: string;
  private readonly partIndex: number;

  constructor(el: Element, eventName: string, partIndex: number) {
    this.el = el;
    this.eventName = eventName;
    this.partIndex = partIndex;
  }

  update(values: readonly unknown[]): void {
    const next = values[this.partIndex];
    this.handler = typeof next === "function" ? (next as (ev: Event) => void) : null;
    if (this.handler && !this.bound) {
      this.el.addEventListener(this.eventName, this.wrapper);
      this.bound = true;
    } else if (!this.handler && this.bound) {
      this.el.removeEventListener(this.eventName, this.wrapper);
      this.bound = false;
    }
  }
}

class BoolAttrPart implements LivePart {
  readonly priority = 1;
  private prev: boolean | undefined = undefined;
  private readonly el: Element;
  private readonly attrName: string;
  private readonly partIndex: number;

  constructor(el: Element, attrName: string, partIndex: number) {
    this.el = el;
    this.attrName = attrName;
    this.partIndex = partIndex;
  }

  update(values: readonly unknown[]): void {
    const next = Boolean(values[this.partIndex] && values[this.partIndex] !== nothing);
    if (next !== this.prev) {
      this.prev = next;
      this.el.toggleAttribute(this.attrName, next);
    }
  }
}

class AttrPart implements LivePart {
  readonly priority = 1;
  private prev: string | symbol | undefined = undefined;
  private readonly el: Element;
  private readonly attrName: string;
  private readonly statics: string[];
  private readonly partIndices: number[];

  constructor(el: Element, attrName: string, statics: string[], partIndices: number[]) {
    this.el = el;
    this.attrName = attrName;
    this.statics = statics;
    this.partIndices = partIndices;
  }

  update(values: readonly unknown[]): void {
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

class PropertyPart implements LivePart {
  // Priority 2 runs AFTER ChildPart (priority 0) so <select> options exist before `.value` is assigned.
  readonly priority = 2;
  private readonly el: Element;
  private readonly propName: string;
  private readonly partIndex: number;

  constructor(el: Element, propName: string, partIndex: number) {
    this.el = el;
    this.propName = propName;
    this.partIndex = partIndex;
  }

  update(values: readonly unknown[]): void {
    const raw = values[this.partIndex];
    const next = raw === nothing || raw === null || raw === undefined ? "" : raw;
    const target = this.el as unknown as Record<string, unknown>;
    if (target[this.propName] !== next) {
      target[this.propName] = next;
    }
  }
}

function isTemplateResult(v: unknown): v is TemplateResult {
  return Boolean(v && typeof v === "object" && (v as TemplateResult)._$litType$ === 1);
}

function isKeyedResult(v: unknown): v is KeyedResult {
  return Boolean(v && typeof v === "object" && (v as KeyedResult)._$litKeyed$ === 1);
}

class TemplateInstance {
  readonly strings: TemplateStringsArray;
  readonly startMarker: Comment;
  readonly endMarker: Comment;
  private readonly parts: LivePart[];

  constructor(compiled: CompiledTemplate) {
    this.strings = compiled.templateEl ? ([] as unknown as TemplateStringsArray) : ([] as unknown as TemplateStringsArray);
    const frag = compiled.templateEl.content.cloneNode(true) as DocumentFragment;
    this.startMarker = document.createComment("latter-i-s");
    this.endMarker = document.createComment("latter-i-e");

    const commentMap = new Map<string, Comment>();
    const walker = document.createTreeWalker(frag, NodeFilter.SHOW_COMMENT);
    let node = walker.nextNode();
    while (node) {
      const c = node as Comment;
      if (c.data.startsWith("latter-p-")) {
        commentMap.set(c.data, c);
      }
      node = walker.nextNode();
    }

    const parts: LivePart[] = [];
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

  private _fragment: DocumentFragment | null;

  mountBefore(parent: Node, refNode: Node | null): void {
    if (this._fragment) {
      parent.insertBefore(this._fragment, refNode);
      this._fragment = null;
    }
  }

  moveBefore(parent: Node, refNode: Node | null): void {
    let cur: Node | null = this.startMarker;
    while (cur) {
      const next: Node | null = cur === this.endMarker ? null : cur.nextSibling;
      parent.insertBefore(cur, refNode);
      cur = next;
    }
  }

  remove(): void {
    let cur: Node | null = this.startMarker;
    while (cur) {
      const next: Node | null = cur === this.endMarker ? null : cur.nextSibling;
      if (cur.parentNode) cur.parentNode.removeChild(cur);
      cur = next;
    }
  }

  update(values: readonly unknown[]): void {
    for (let i = 0; i < this.parts.length; i += 1) {
      this.parts[i].update(values);
    }
  }
}

function createInstance(res: TemplateResult): { strings: TemplateStringsArray; inst: TemplateInstance } {
  const compiled = compileTemplate(res.strings);
  const inst = new TemplateInstance(compiled);
  return { strings: res.strings, inst };
}

class ChildPart implements LivePart {
  readonly priority = 0;
  private mode: "empty" | "text" | "template" | "array" | "keyed" = "empty";
  private textNode: Text | null = null;
  private singleEntry: { strings: TemplateStringsArray; inst: TemplateInstance } | null = null;
  private arrayEntries: Array<{ strings: TemplateStringsArray; inst: TemplateInstance }> = [];
  private keyedMap = new Map<unknown, { strings: TemplateStringsArray; inst: TemplateInstance }>();

  private readonly startMarker: Comment;
  private readonly endMarker: Comment;
  private readonly partIndex: number;

  constructor(startMarker: Comment, endMarker: Comment, partIndex: number) {
    this.startMarker = startMarker;
    this.endMarker = endMarker;
    this.partIndex = partIndex;
  }

  private clearBetween(): void {
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

  update(values: readonly unknown[]): void {
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
      const nextMap = new Map<unknown, { strings: TemplateStringsArray; inst: TemplateInstance }>();
      const ordered: Array<{ strings: TemplateStringsArray; inst: TemplateInstance }> = [];
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
      let cursor: Node = this.endMarker;
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
      const tpls: TemplateResult[] = [];
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

  private setText(parent: Node, str: string): void {
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

export class LitElement extends HTMLElement implements ReactiveControllerHost {
  static styles?: CSSResult | CSSResult[];

  readonly renderRoot: ShadowRoot;
  private readonly _controllers = new Set<ReactiveController>();
  private _updatePending = false;
  private _hasUpdated = false;
  private _resolveUpdate: ((val: boolean) => void) | null = null;
  private _updatePromise: Promise<boolean> = Promise.resolve(true);
  private _rootEntry: { strings: TemplateStringsArray; inst: TemplateInstance } | null = null;
  private _stylesAdopted = false;

  constructor() {
    super();
    this.renderRoot = this.attachShadow({ mode: "open" });
  }

  addController(controller: ReactiveController): void {
    this._controllers.add(controller);
    if (this.isConnected && controller.hostConnected) {
      controller.hostConnected();
    }
  }

  removeController(controller: ReactiveController): void {
    this._controllers.delete(controller);
  }

  connectedCallback(): void {
    this._adoptStylesOnce();
    for (const c of this._controllers) {
      c.hostConnected?.();
    }
    this.requestUpdate();
  }

  disconnectedCallback(): void {
    for (const c of this._controllers) {
      c.hostDisconnected?.();
    }
  }

  get updateComplete(): Promise<boolean> {
    return this._updatePromise;
  }

  requestUpdate(): void {
    if (this._updatePending) return;
    this._updatePending = true;
    this._updatePromise = new Promise<boolean>((resolve) => {
      this._resolveUpdate = resolve;
    });
    queueMicrotask(() => this._performUpdate());
  }

  private _adoptStylesOnce(): void {
    if (this._stylesAdopted) return;
    this._stylesAdopted = true;
    const ctor = this.constructor as typeof LitElement;
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

  private _performUpdate(): void {
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

  protected render(): TemplateResult | symbol {
    return nothing;
  }

  protected firstUpdated(): void {}

  protected updated(): void {}
}
