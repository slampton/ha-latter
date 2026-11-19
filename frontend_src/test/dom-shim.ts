/**
 * Lightweight zero-dependency DOM & Custom Elements shim for Node 24+ `node --test`.
 * Supports vendored `lit-html` v3.3.3 (`<template>`, `<?lit$...$>` comment markers, `TreeWalker`),
 * `LitElement` (`ShadowRoot`, `CSSStyleSheet`, `adoptedStyleSheets`), and interactive controls.
 */

const VOID_TAGS = new Set([
  "AREA",
  "BASE",
  "BR",
  "COL",
  "EMBED",
  "HR",
  "IMG",
  "INPUT",
  "LINK",
  "META",
  "PARAM",
  "SOURCE",
  "TRACK",
  "WBR",
]);

function decodeEntities(raw: string): string {
  if (!raw.includes("&")) return raw;
  return raw.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (full, ent: string) => {
    if (ent === "amp") return "&";
    if (ent === "lt") return "<";
    if (ent === "gt") return ">";
    if (ent === "quot") return '"';
    if (ent === "apos" || ent === "#39") return "'";
    if (ent === "nbsp") return "\u00a0";
    if (ent === "larr") return "←";
    if (ent === "rarr") return "→";
    if (ent.startsWith("#x") || ent.startsWith("#X")) {
      const code = Number.parseInt(ent.slice(2), 16);
      return Number.isFinite(code) ? String.fromCodePoint(code) : full;
    }
    if (ent.startsWith("#")) {
      const code = Number.parseInt(ent.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : full;
    }
    return full;
  });
}

function escapeHtmlText(raw: string): string {
  return raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeHtmlAttr(raw: string): string {
  return escapeHtmlText(raw).replace(/"/g, "&quot;");
}

type ListenerFn = (ev: SimEvent) => void;
type ListenerObj = { handleEvent: (ev: SimEvent) => void };
type Listener = ListenerFn | ListenerObj;

export class SimEvent {
  readonly type: string;
  readonly bubbles: boolean;
  readonly cancelable: boolean;
  readonly composed: boolean;
  defaultPrevented = false;
  propagationStopped = false;
  immediatePropagationStopped = false;
  target: unknown = null;
  currentTarget: unknown = null;

  constructor(type: string, init?: EventInit) {
    this.type = String(type);
    this.bubbles = Boolean(init?.bubbles);
    this.cancelable = init?.cancelable !== false;
    this.composed = Boolean(init?.composed);
  }

  preventDefault(): void {
    if (this.cancelable) {
      this.defaultPrevented = true;
    }
  }

  stopPropagation(): void {
    this.propagationStopped = true;
  }

  stopImmediatePropagation(): void {
    this.immediatePropagationStopped = true;
    this.propagationStopped = true;
  }

  composedPath(): unknown[] {
    const path: unknown[] = [];
    let cur = this.target as SimNode | null;
    while (cur) {
      path.push(cur);
      if (cur.nodeType === 11 && "host" in cur) {
        cur = (cur as SimShadowRoot).host;
      } else {
        cur = cur.parentNode;
      }
    }
    return path;
  }
}

export class SimCustomEvent<T = unknown> extends SimEvent {
  readonly detail: T;
  constructor(type: string, init?: CustomEventInit<T>) {
    super(type, init);
    this.detail = (init?.detail ?? null) as T;
  }
}

export class SimKeyboardEvent extends SimEvent {
  readonly key: string;
  readonly code: string;
  readonly keyCode: number;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly altKey: boolean;
  readonly shiftKey: boolean;
  readonly isComposing: boolean;

  constructor(type: string, init?: KeyboardEventInit & { keyCode?: number }) {
    super(type, init);
    this.key = init?.key ?? "";
    this.code = init?.code ?? "";
    this.keyCode = init?.keyCode ?? 0;
    this.ctrlKey = Boolean(init?.ctrlKey);
    this.metaKey = Boolean(init?.metaKey);
    this.altKey = Boolean(init?.altKey);
    this.shiftKey = Boolean(init?.shiftKey);
    this.isComposing = Boolean(init?.isComposing);
  }
}

export class SimFocusEvent extends SimEvent {
  readonly relatedTarget: unknown;
  constructor(type: string, init?: FocusEventInit) {
    super(type, init);
    this.relatedTarget = init?.relatedTarget ?? null;
  }
}

export class SimMouseEvent extends SimEvent {
  readonly button: number;
  readonly clientX: number;
  readonly clientY: number;
  constructor(type: string, init?: MouseEventInit) {
    super(type, init);
    this.button = init?.button ?? 0;
    this.clientX = init?.clientX ?? 0;
    this.clientY = init?.clientY ?? 0;
  }
}

export class SimNode {
  nodeType = 0;
  parentNode: SimNode | null = null;
  childNodes: SimNode[] = [];
  ownerDocument: SimDocument | null = null;
  private readonly _listeners = new Map<string, Listener[]>();

  get firstChild(): SimNode | null {
    return this.childNodes[0] ?? null;
  }

  get lastChild(): SimNode | null {
    return this.childNodes[this.childNodes.length - 1] ?? null;
  }

  get nextSibling(): SimNode | null {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.childNodes;
    const idx = siblings.indexOf(this);
    return idx >= 0 && idx + 1 < siblings.length ? siblings[idx + 1] : null;
  }

  get previousSibling(): SimNode | null {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.childNodes;
    const idx = siblings.indexOf(this);
    return idx > 0 ? siblings[idx - 1] : null;
  }

  get parentElement(): SimElement | null {
    return this.parentNode && this.parentNode.nodeType === 1
      ? (this.parentNode as SimElement)
      : null;
  }

  get isConnected(): boolean {
    let cur: SimNode | null = this;
    while (cur) {
      if (cur.nodeType === 9) return true;
      if (cur.nodeType === 11 && "host" in cur) {
        cur = (cur as SimShadowRoot).host;
      } else {
        cur = cur.parentNode;
      }
    }
    return false;
  }

  getRootNode(): SimNode {
    let cur: SimNode = this;
    while (cur.parentNode) {
      cur = cur.parentNode;
    }
    return cur;
  }

  contains(other: SimNode | null | undefined): boolean {
    let cur: SimNode | null | undefined = other;
    while (cur) {
      if (cur === this) return true;
      cur = cur.parentNode;
    }
    return false;
  }

  appendChild<T extends SimNode>(node: T): T {
    return this.insertBefore(node, null);
  }

  insertBefore<T extends SimNode>(node: T, refNode: SimNode | null): T {
    const wasConnected = this.isConnected;
    if ((node as SimNode).nodeType === 11 && !("host" in node)) {
      const moving = [...node.childNodes];
      node.childNodes.length = 0;
      for (const child of moving) {
        child.parentNode = null;
        this.insertBefore(child, refNode);
      }
      return node;
    }
    if (node.parentNode) {
      node.parentNode.removeChild(node);
    }
    const refIdx = refNode ? this.childNodes.indexOf(refNode) : -1;
    if (refNode && refIdx === -1) {
      throw new Error("insertBefore reference node is not a child of this node");
    }
    node.parentNode = this;
    if (refIdx === -1) {
      this.childNodes.push(node);
    } else {
      this.childNodes.splice(refIdx, 0, node);
    }
    if (wasConnected) {
      notifySubtreeConnected(node, true);
    }
    return node;
  }

  removeChild<T extends SimNode>(node: T): T {
    const wasConnected = node.isConnected;
    const idx = this.childNodes.indexOf(node);
    if (idx === -1) {
      throw new Error("removeChild node is not a child of this node");
    }
    this.childNodes.splice(idx, 1);
    node.parentNode = null;
    if (wasConnected) {
      notifySubtreeConnected(node, false);
    }
    return node;
  }

  remove(): void {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  append(...items: Array<SimNode | string>): void {
    const doc = this.ownerDocument ?? simDocument;
    for (const item of items) {
      const node = typeof item === "string" ? doc.createTextNode(item) : item;
      this.appendChild(node);
    }
  }

  replaceWith(...items: Array<SimNode | string>): void {
    const parent = this.parentNode;
    if (!parent) return;
    const doc = this.ownerDocument ?? simDocument;
    for (const item of items) {
      const node = typeof item === "string" ? doc.createTextNode(item) : item;
      parent.insertBefore(node, this);
    }
    parent.removeChild(this);
  }

  get textContent(): string {
    return this.childNodes
      .filter((c) => c.nodeType !== 8)
      .map((c) => c.textContent)
      .join("");
  }

  set textContent(val: string) {
    while (this.childNodes.length > 0) {
      this.removeChild(this.childNodes[0]);
    }
    const str = String(val ?? "");
    if (str) {
      const doc = this.ownerDocument ?? simDocument;
      this.appendChild(doc.createTextNode(str));
    }
  }

  cloneNode(deep = false): SimNode {
    const copy = new SimNode();
    copy.nodeType = this.nodeType;
    copy.ownerDocument = this.ownerDocument;
    if (deep) {
      for (const c of this.childNodes) {
        copy.appendChild(c.cloneNode(true));
      }
    }
    return copy;
  }

  addEventListener(type: string, listener: Listener | null): void {
    if (!listener) return;
    let list = this._listeners.get(type);
    if (!list) {
      list = [];
      this._listeners.set(type, list);
    }
    if (!list.includes(listener)) {
      list.push(listener);
    }
  }

  removeEventListener(type: string, listener: Listener | null): void {
    if (!listener) return;
    const list = this._listeners.get(type);
    if (!list) return;
    const idx = list.indexOf(listener);
    if (idx >= 0) {
      list.splice(idx, 1);
    }
  }

  dispatchEvent(ev: SimEvent): boolean {
    if (!ev.target) {
      Object.defineProperty(ev, "target", {
        value: this,
        configurable: true,
        writable: true,
      });
    }
    const path: SimNode[] = [];
    let cur: SimNode | null = this;
    while (cur) {
      path.push(cur);
      if (!ev.bubbles) break;
      cur = cur.parentNode;
    }
    for (const node of path) {
      Object.defineProperty(ev, "currentTarget", {
        value: node,
        configurable: true,
        writable: true,
      });
      const list = node._listeners.get(ev.type);
      if (list) {
        for (const l of [...list]) {
          if (typeof l === "function") {
            l.call(node, ev);
          } else if (typeof l.handleEvent === "function") {
            l.handleEvent(ev);
          }
          if (ev.immediatePropagationStopped) break;
        }
      }
      if (ev.propagationStopped) break;
    }
    return !ev.defaultPrevented;
  }
}

function notifySubtreeConnected(node: SimNode, connected: boolean): void {
  if (node.nodeType === 1) {
    const el = node as SimElement & {
      connectedCallback?: () => void;
      disconnectedCallback?: () => void;
    };
    if (connected) {
      el.connectedCallback?.();
    } else {
      el.disconnectedCallback?.();
    }
  }
  for (const child of [...node.childNodes]) {
    notifySubtreeConnected(child, connected);
  }
}

export class SimText extends SimNode {
  data: string;
  constructor(data = "") {
    super();
    this.nodeType = 3;
    this.data = String(data);
  }
  override get textContent(): string {
    return this.data;
  }
  override set textContent(val: string) {
    this.data = String(val ?? "");
  }
  override cloneNode(): SimText {
    const t = new SimText(this.data);
    t.ownerDocument = this.ownerDocument;
    return t;
  }
}

export class SimComment extends SimNode {
  data: string;
  constructor(data = "") {
    super();
    this.nodeType = 8;
    this.data = String(data);
  }
  override get textContent(): string {
    return this.data;
  }
  override set textContent(val: string) {
    this.data = String(val ?? "");
  }
  override cloneNode(): SimComment {
    const c = new SimComment(this.data);
    c.ownerDocument = this.ownerDocument;
    return c;
  }
}

class SimClassList {
  private readonly _el: SimElement;
  constructor(el: SimElement) {
    this._el = el;
  }
  private _set(): Set<string> {
    const raw = this._el.getAttribute("class") || "";
    return new Set(raw.split(/\s+/).filter(Boolean));
  }
  private _write(s: Set<string>): void {
    this._el.setAttribute("class", [...s].join(" "));
  }
  contains(cls: string): boolean {
    return this._set().has(cls);
  }
  add(...tokens: string[]): void {
    const s = this._set();
    for (const tok of tokens) {
      if (tok) s.add(tok);
    }
    this._write(s);
  }
  remove(...tokens: string[]): void {
    const s = this._set();
    for (const tok of tokens) {
      s.delete(tok);
    }
    this._write(s);
  }
  toggle(tok: string, force?: boolean): boolean {
    const s = this._set();
    const want = force !== undefined ? force : !s.has(tok);
    if (want) s.add(tok);
    else s.delete(tok);
    this._write(s);
    return want;
  }
}

export class SimCSSStyleSheet {
  cssText = "";
  replaceSync(text: string): void {
    this.cssText = String(text ?? "");
  }
}

export class SimDocumentFragment extends SimNode {
  constructor() {
    super();
    this.nodeType = 11;
  }

  get children(): SimElement[] {
    return this.childNodes.filter((n): n is SimElement => n.nodeType === 1);
  }

  get innerHTML(): string {
    return serializeChildren(this);
  }

  set innerHTML(markup: string) {
    while (this.childNodes.length > 0) {
      this.removeChild(this.childNodes[0]);
    }
    parseHtmlInto(String(markup ?? ""), this, this.ownerDocument ?? simDocument);
  }

  getElementById(id: string): SimElement | null {
    return findFirstElement(this, (el) => el.id === id);
  }

  querySelector(selector: string): SimElement | null {
    return queryElements(this, selector, true)[0] ?? null;
  }

  querySelectorAll(selector: string): SimElement[] {
    return queryElements(this, selector, false);
  }

  override cloneNode(deep = false): SimDocumentFragment {
    const frag = new SimDocumentFragment();
    frag.ownerDocument = this.ownerDocument;
    if (deep) {
      for (const c of this.childNodes) {
        frag.appendChild(c.cloneNode(true));
      }
    }
    return frag;
  }
}

export class SimShadowRoot extends SimDocumentFragment {
  readonly host: SimElement;
  readonly mode: "open" | "closed";
  adoptedStyleSheets: SimCSSStyleSheet[] = [];
  activeElement: SimElement | null = null;

  constructor(host: SimElement, mode: "open" | "closed" = "open") {
    super();
    this.host = host;
    this.mode = mode;
  }
}

export class SimElement extends SimNode {
  readonly tagName: string;
  private readonly _attrs = new Map<string, string>();
  readonly classList: SimClassList;
  readonly style: Record<string, string> = {};
  shadowRoot: SimShadowRoot | null = null;

  constructor(tagName = "DIV") {
    super();
    this.nodeType = 1;
    this.tagName = String(tagName).toUpperCase();
    this.classList = new SimClassList(this);
  }

  get children(): SimElement[] {
    return this.childNodes.filter((n): n is SimElement => n.nodeType === 1);
  }

  get nextElementSibling(): SimElement | null {
    let cur = this.nextSibling;
    while (cur) {
      if (cur.nodeType === 1) return cur as SimElement;
      cur = cur.nextSibling;
    }
    return null;
  }

  get previousElementSibling(): SimElement | null {
    let cur = this.previousSibling;
    while (cur) {
      if (cur.nodeType === 1) return cur as SimElement;
      cur = cur.previousSibling;
    }
    return null;
  }

  get id(): string {
    return this._attrs.get("id") ?? "";
  }
  set id(val: string) {
    this.setAttribute("id", String(val ?? ""));
  }

  get className(): string {
    return this._attrs.get("class") ?? "";
  }
  set className(val: string) {
    this.setAttribute("class", String(val ?? ""));
  }

  get disabled(): boolean {
    return this._attrs.has("disabled");
  }
  set disabled(val: boolean) {
    this.toggleAttribute("disabled", Boolean(val));
  }

  hasAttributes(): boolean {
    return this._attrs.size > 0;
  }

  getAttributeNames(): string[] {
    return [...this._attrs.keys()];
  }

  hasAttribute(name: string): boolean {
    return this._attrs.has(name.toLowerCase());
  }

  getAttribute(name: string): string | null {
    const v = this._attrs.get(name.toLowerCase());
    return v === undefined ? null : v;
  }

  setAttribute(name: string, value: string): void {
    const key = name.toLowerCase();
    const str = String(value ?? "");
    this._attrs.set(key, str);
    this._onAttributeChanged(key, str);
  }

  removeAttribute(name: string): void {
    const key = name.toLowerCase();
    this._attrs.delete(key);
    this._onAttributeChanged(key, null);
  }

  toggleAttribute(name: string, force?: boolean): boolean {
    const key = name.toLowerCase();
    const want = force !== undefined ? force : !this._attrs.has(key);
    if (want) {
      if (!this._attrs.has(key)) {
        this.setAttribute(key, "");
      }
      return true;
    }
    this.removeAttribute(key);
    return false;
  }

  protected _onAttributeChanged(_key: string, _val: string | null): void {}

  attachShadow(init: { mode: "open" | "closed" }): SimShadowRoot {
    const root = new SimShadowRoot(this, init.mode);
    root.ownerDocument = this.ownerDocument ?? simDocument;
    if (init.mode === "open") {
      this.shadowRoot = root;
    }
    return root;
  }

  focus(): void {
    const root = this.getRootNode();
    if (root instanceof SimShadowRoot) {
      root.activeElement = this;
      if (this.ownerDocument) {
        this.ownerDocument.activeElement = root.host;
      }
    } else if (root instanceof SimDocument) {
      root.activeElement = this;
    } else {
      simDocument.activeElement = this;
    }
    this.dispatchEvent(new SimFocusEvent("focus", { bubbles: false }));
    this.dispatchEvent(new SimFocusEvent("focusin", { bubbles: true }));
  }

  blur(): void {
    const root = this.getRootNode();
    if (root instanceof SimShadowRoot && root.activeElement === this) {
      root.activeElement = null;
    }
    if (root instanceof SimDocument && root.activeElement === this) {
      root.activeElement = null;
    }
    if (simDocument.activeElement === this) {
      simDocument.activeElement = null;
    }
    this.dispatchEvent(new SimFocusEvent("blur", { bubbles: false }));
    this.dispatchEvent(new SimFocusEvent("focusout", { bubbles: true }));
  }

  click(): void {
    if (this.disabled) return;
    this.dispatchEvent(new SimMouseEvent("click", { bubbles: true, cancelable: true }));
  }

  scrollIntoView(): void {}

  get innerHTML(): string {
    return serializeChildren(this);
  }

  set innerHTML(markup: string) {
    while (this.childNodes.length > 0) {
      this.removeChild(this.childNodes[0]);
    }
    parseHtmlInto(String(markup ?? ""), this, this.ownerDocument ?? simDocument);
  }

  get outerHTML(): string {
    return serializeElement(this);
  }

  getElementById(id: string): SimElement | null {
    return findFirstElement(this, (el) => el.id === id);
  }

  querySelector(selector: string): SimElement | null {
    return queryElements(this, selector, true)[0] ?? null;
  }

  querySelectorAll(selector: string): SimElement[] {
    return queryElements(this, selector, false);
  }

  closest(selector: string): SimElement | null {
    let cur: SimElement | null = this;
    while (cur) {
      if (matchesSelectorGroup(cur, selector)) return cur;
      cur = cur.parentElement;
    }
    return null;
  }

  override cloneNode(deep = false): SimElement {
    const doc = this.ownerDocument ?? simDocument;
    const copy = doc.createElement(this.tagName);
    for (const name of this.getAttributeNames()) {
      copy.setAttribute(name, this.getAttribute(name) ?? "");
    }
    if (deep) {
      for (const c of this.childNodes) {
        copy.appendChild(c.cloneNode(true));
      }
    }
    return copy;
  }
}

export class SimHTMLTemplateElement extends SimElement {
  readonly content: SimDocumentFragment;
  constructor() {
    super("TEMPLATE");
    this.content = new SimDocumentFragment();
    this.content.ownerDocument = simDocument;
  }
  override get innerHTML(): string {
    return this.content.innerHTML;
  }
  override set innerHTML(markup: string) {
    this.content.innerHTML = markup;
  }
  override cloneNode(deep = false): SimHTMLTemplateElement {
    const copy = new SimHTMLTemplateElement();
    copy.ownerDocument = this.ownerDocument;
    for (const name of this.getAttributeNames()) {
      copy.setAttribute(name, this.getAttribute(name) ?? "");
    }
    if (deep) {
      for (const c of this.content.childNodes) {
        copy.content.appendChild(c.cloneNode(true));
      }
    }
    return copy;
  }
}

export class SimHTMLInputElement extends SimElement {
  private _value = "";
  private _dirtyValue = false;
  checked = false;

  constructor() {
    super("INPUT");
  }

  get type(): string {
    return (this.getAttribute("type") || "text").toLowerCase();
  }
  set type(val: string) {
    this.setAttribute("type", String(val || "text"));
  }

  get value(): string {
    return this._value;
  }
  set value(val: string) {
    this._dirtyValue = true;
    this._value = String(val ?? "");
  }

  protected override _onAttributeChanged(key: string, val: string | null): void {
    if (key === "value" && !this._dirtyValue) {
      this._value = val ?? "";
    }
    if (key === "checked") {
      this.checked = val !== null;
    }
  }
}

export class SimHTMLTextAreaElement extends SimElement {
  private _value = "";
  private _dirtyValue = false;

  constructor() {
    super("TEXTAREA");
  }

  get value(): string {
    return this._dirtyValue ? this._value : this.textContent;
  }
  set value(val: string) {
    this._dirtyValue = true;
    this._value = String(val ?? "");
  }
}

export class SimHTMLOptionElement extends SimElement {
  selected = false;
  constructor() {
    super("OPTION");
  }
  get value(): string {
    const attr = this.getAttribute("value");
    return attr !== null ? attr : this.textContent;
  }
  set value(val: string) {
    this.setAttribute("value", String(val ?? ""));
  }
  protected override _onAttributeChanged(key: string, val: string | null): void {
    if (key === "selected") {
      this.selected = val !== null;
    }
  }
}

export class SimHTMLSelectElement extends SimElement {
  private _value: string | null = null;
  constructor() {
    super("SELECT");
  }
  get options(): SimHTMLOptionElement[] {
    const out: SimHTMLOptionElement[] = [];
    walkElements(this, (el) => {
      if (el.tagName === "OPTION") out.push(el as SimHTMLOptionElement);
    });
    return out;
  }
  get value(): string {
    if (this._value !== null) return this._value;
    const opts = this.options;
    const sel = opts.find((o) => o.selected) ?? opts[0];
    return sel ? sel.value : "";
  }
  set value(val: string) {
    const str = String(val ?? "");
    this._value = str;
    for (const o of this.options) {
      o.selected = o.value === str;
    }
  }
}

export class SimHTMLDialogElement extends SimElement {
  constructor() {
    super("DIALOG");
  }
  get open(): boolean {
    return this.hasAttribute("open");
  }
  set open(val: boolean) {
    this.toggleAttribute("open", Boolean(val));
  }
  showModal(): void {
    this.setAttribute("open", "");
  }
  close(): void {
    this.removeAttribute("open");
    this.dispatchEvent(new SimEvent("close"));
  }
}

class SimTreeWalker {
  readonly root: SimNode;
  readonly whatToShow: number;
  currentNode: SimNode;

  constructor(root: SimNode, whatToShow = 0xffffffff) {
    this.root = root;
    this.whatToShow = whatToShow >>> 0;
    this.currentNode = root;
  }

  private _accept(node: SimNode): boolean {
    const bit = 1 << (node.nodeType - 1);
    return (this.whatToShow & bit) !== 0;
  }

  private _stepNext(from: SimNode): SimNode | null {
    if (from.firstChild) {
      return from.firstChild;
    }
    let cur: SimNode | null = from;
    while (cur && cur !== this.root) {
      if (cur.nextSibling) {
        return cur.nextSibling;
      }
      cur = cur.parentNode;
    }
    return null;
  }

  nextNode(): SimNode | null {
    let cur = this._stepNext(this.currentNode);
    while (cur) {
      if (this._accept(cur)) {
        this.currentNode = cur;
        return cur;
      }
      cur = this._stepNext(cur);
    }
    return null;
  }
}

const CUSTOM_ELEMENT_REGISTRY = new Map<string, CustomElementConstructor>();

const simCustomElements = {
  define(name: string, ctor: CustomElementConstructor): void {
    const key = String(name).toLowerCase();
    if (!CUSTOM_ELEMENT_REGISTRY.has(key)) {
      CUSTOM_ELEMENT_REGISTRY.set(key, ctor);
    }
  },
  get(name: string): CustomElementConstructor | undefined {
    return CUSTOM_ELEMENT_REGISTRY.get(String(name).toLowerCase());
  },
};

export class SimDocument extends SimNode {
  readonly body: SimElement;
  activeElement: SimElement | null = null;

  constructor() {
    super();
    this.nodeType = 9;
    this.ownerDocument = this;
    this.body = new SimElement("BODY");
    this.body.ownerDocument = this;
    this.appendChild(this.body);
  }

  createElement(tagName: string): SimElement {
    const lower = String(tagName).toLowerCase();
    const customCtor = CUSTOM_ELEMENT_REGISTRY.get(lower);
    let el: SimElement;
    if (customCtor) {
      el = new (customCtor as unknown as new () => SimElement)();
      (el as { tagName: string }).tagName = lower.toUpperCase();
    } else if (lower === "template") {
      el = new SimHTMLTemplateElement();
    } else if (lower === "input") {
      el = new SimHTMLInputElement();
    } else if (lower === "textarea") {
      el = new SimHTMLTextAreaElement();
    } else if (lower === "select") {
      el = new SimHTMLSelectElement();
    } else if (lower === "option") {
      el = new SimHTMLOptionElement();
    } else if (lower === "dialog") {
      el = new SimHTMLDialogElement();
    } else {
      el = new SimElement(lower.toUpperCase());
    }
    el.ownerDocument = this;
    return el;
  }

  createElementNS(_ns: string, tagName: string): SimElement {
    return this.createElement(tagName);
  }

  createTextNode(data: string): SimText {
    const node = new SimText(data);
    node.ownerDocument = this;
    return node;
  }

  createComment(data: string): SimComment {
    const node = new SimComment(data);
    node.ownerDocument = this;
    return node;
  }

  createDocumentFragment(): SimDocumentFragment {
    const frag = new SimDocumentFragment();
    frag.ownerDocument = this;
    return frag;
  }

  importNode<T extends SimNode>(node: T, deep = false): T {
    const cloned = node.cloneNode(deep) as T;
    cloned.ownerDocument = this;
    return cloned;
  }

  createTreeWalker(root: SimNode, whatToShow = 0xffffffff): SimTreeWalker {
    return new SimTreeWalker(root, whatToShow);
  }

  getElementById(id: string): SimElement | null {
    return findFirstElement(this, (el) => el.id === id);
  }

  querySelector(selector: string): SimElement | null {
    return queryElements(this, selector, true)[0] ?? null;
  }

  querySelectorAll(selector: string): SimElement[] {
    return queryElements(this, selector, false);
  }
}

function parseAttributes(attrText: string, el: SimElement): void {
  let i = 0;
  const n = attrText.length;
  while (i < n) {
    while (i < n && /\s/.test(attrText[i])) i += 1;
    if (i >= n || attrText[i] === "/") {
      i += 1;
      continue;
    }
    let nameEnd = i;
    while (nameEnd < n && !/[\s=/>]/.test(attrText[nameEnd])) {
      nameEnd += 1;
    }
    const rawName = attrText.slice(i, nameEnd);
    i = nameEnd;
    if (!rawName) {
      i += 1;
      continue;
    }
    while (i < n && /\s/.test(attrText[i])) i += 1;
    let val = "";
    if (i < n && attrText[i] === "=") {
      i += 1;
      while (i < n && /\s/.test(attrText[i])) i += 1;
      if (i < n && (attrText[i] === '"' || attrText[i] === "'")) {
        const q = attrText[i];
        i += 1;
        const start = i;
        while (i < n && attrText[i] !== q) i += 1;
        val = decodeEntities(attrText.slice(start, i));
        if (i < n && attrText[i] === q) i += 1;
      } else {
        const start = i;
        while (i < n && !/[\s>]/.test(attrText[i])) i += 1;
        val = decodeEntities(attrText.slice(start, i));
      }
    }
    el.setAttribute(rawName, val);
  }
}

function parseHtmlInto(html: string, root: SimNode, doc: SimDocument): void {
  const stack: SimNode[] = [root];
  let i = 0;
  const n = html.length;

  while (i < n) {
    const curParent = stack[stack.length - 1];
    const lt = html.indexOf("<", i);
    if (lt === -1) {
      const tail = decodeEntities(html.slice(i));
      if (tail) curParent.appendChild(doc.createTextNode(tail));
      break;
    }
    if (lt > i) {
      const text = decodeEntities(html.slice(i, lt));
      if (text) curParent.appendChild(doc.createTextNode(text));
    }
    if (html.startsWith("<!--", lt)) {
      const end = html.indexOf("-->", lt + 4);
      if (end === -1) {
        curParent.appendChild(doc.createComment(html.slice(lt + 4)));
        break;
      }
      curParent.appendChild(doc.createComment(html.slice(lt + 4, end)));
      i = end + 3;
      continue;
    }
    // HTML5 bogus comment state used by `lit-html` (`<?lit$...$>` and `<?>`)
    if (html[lt + 1] === "?") {
      const gt = html.indexOf(">", lt + 1);
      if (gt === -1) {
        curParent.appendChild(doc.createComment(html.slice(lt + 1)));
        break;
      }
      curParent.appendChild(doc.createComment(html.slice(lt + 1, gt)));
      i = gt + 1;
      continue;
    }
    // Closing tag `</tag>`
    if (html[lt + 1] === "/") {
      const gt = html.indexOf(">", lt + 2);
      if (gt === -1) break;
      const closeTag = html
        .slice(lt + 2, gt)
        .trim()
        .toUpperCase();
      for (let s = stack.length - 1; s >= 1; s -= 1) {
        const candidate = stack[s];
        if (candidate.nodeType === 1 && (candidate as SimElement).tagName === closeTag) {
          stack.length = s;
          break;
        }
      }
      i = gt + 1;
      continue;
    }

    // Opening tag `<tag ...>`
    let gt = lt + 1;
    let quote: string | null = null;
    while (gt < n) {
      const ch = html[gt];
      if (quote) {
        if (ch === quote) quote = null;
      } else if (ch === '"' || ch === "'") {
        quote = ch;
      } else if (ch === ">") {
        break;
      }
      gt += 1;
    }
    if (gt >= n) {
      curParent.appendChild(doc.createTextNode(decodeEntities(html.slice(lt))));
      break;
    }

    const inside = html.slice(lt + 1, gt);
    const selfClosing = inside.trimEnd().endsWith("/");
    const bodyWithoutSlash = selfClosing ? inside.replace(/\/\s*$/, "") : inside;
    const mTag = /^([A-Za-z][A-Za-z0-9:_-]*)([\s\S]*)$/.exec(bodyWithoutSlash.trimStart());
    if (!mTag) {
      curParent.appendChild(doc.createComment(inside));
      i = gt + 1;
      continue;
    }

    const tagName = mTag[1];
    const attrStr = mTag[2] || "";
    const el = doc.createElement(tagName);
    parseAttributes(attrStr, el);

    const targetContainer =
      el instanceof SimHTMLTemplateElement ? el.content : el;
    curParent.appendChild(el);
    i = gt + 1;

    const upper = el.tagName;
    if (upper === "TEXTAREA" || upper === "STYLE" || upper === "SCRIPT" || upper === "TITLE") {
      const closeRe = new RegExp(`</${tagName}\\s*>`, "i");
      const mClose = closeRe.exec(html.slice(i));
      if (mClose) {
        const rawInner = html.slice(i, i + mClose.index);
        if (rawInner) {
          el.appendChild(doc.createTextNode(decodeEntities(rawInner)));
        }
        i += mClose.index + mClose[0].length;
      }
      continue;
    }

    if (!selfClosing && !VOID_TAGS.has(upper)) {
      stack.push(targetContainer);
    }
  }
}

function serializeChildren(parent: SimNode): string {
  return parent.childNodes
    .map((child) => {
      if (child.nodeType === 3) return escapeHtmlText((child as SimText).data);
      if (child.nodeType === 8) return `<!--${(child as SimComment).data}-->`;
      if (child.nodeType === 1) return serializeElement(child as SimElement);
      return "";
    })
    .join("");
}

function serializeElement(el: SimElement): string {
  const tag = el.tagName.toLowerCase();
  const attrs = el
    .getAttributeNames()
    .map((k) => {
      const v = el.getAttribute(k) ?? "";
      return v === "" ? k : `${k}="${escapeHtmlAttr(v)}"`;
    })
    .join(" ");
  const open = attrs ? `<${tag} ${attrs}>` : `<${tag}>`;
  if (VOID_TAGS.has(el.tagName)) {
    return open;
  }
  const inner =
    el instanceof SimHTMLTemplateElement ? el.content.innerHTML : serializeChildren(el);
  return `${open}${inner}</${tag}>`;
}

function walkElements(root: SimNode, fn: (el: SimElement) => boolean | void): boolean {
  for (const child of root.childNodes) {
    if (child.nodeType === 1) {
      if (fn(child as SimElement) === true) return true;
    }
    if (walkElements(child, fn) === true) return true;
  }
  return false;
}

function findFirstElement(
  root: SimNode,
  pred: (el: SimElement) => boolean,
): SimElement | null {
  let found: SimElement | null = null;
  walkElements(root, (el) => {
    if (pred(el)) {
      found = el;
      return true;
    }
  });
  return found;
}

function matchesSingleCompoundSelector(el: SimElement, compound: string): boolean {
  let rest = compound.trim();
  if (!rest) return false;

  // Handle `:not(...)` pseudo-selectors
  const notClauses: string[] = [];
  rest = rest.replace(/:not\(([^)]+)\)/g, (_m, inner: string) => {
    notClauses.push(inner.trim());
    return "";
  });
  for (const neg of notClauses) {
    if (matchesSingleCompoundSelector(el, neg)) return false;
  }

  if (rest.includes(":disabled")) {
    if (!el.disabled) return false;
    rest = rest.replace(/:disabled/g, "");
  }

  // Handle `[attr]` / `[attr='val']` / `[attr="val"]`
  const attrClauses: Array<{ name: string; val: string | null }> = [];
  rest = rest.replace(
    /\[\s*([A-Za-z0-9_:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\]]*)))?\s*\]/g,
    (_m, name: string, dq?: string, sq?: string, uq?: string) => {
      const rawVal = dq !== undefined ? dq : sq !== undefined ? sq : uq !== undefined ? uq.trim() : null;
      const val = rawVal !== null ? rawVal.replace(/\\(.)/g, "$1") : null;
      attrClauses.push({ name: name.toLowerCase(), val });
      return "";
    },
  );
  for (const ac of attrClauses) {
    if (!el.hasAttribute(ac.name)) return false;
    if (ac.val !== null && el.getAttribute(ac.name) !== ac.val) return false;
  }

  // Handle `#id` and `.class` and leading tag name
  const idMatches = [...rest.matchAll(/#([A-Za-z0-9_:-]+)/g)];
  for (const m of idMatches) {
    if (el.id !== m[1]) return false;
  }
  rest = rest.replace(/#[A-Za-z0-9_:-]+/g, "");

  const clsMatches = [...rest.matchAll(/\.([A-Za-z0-9_:-]+)/g)];
  for (const m of clsMatches) {
    if (!el.classList.contains(m[1])) return false;
  }
  rest = rest.replace(/\.[A-Za-z0-9_:-]+/g, "").trim();

  if (rest && rest !== "*") {
    if (el.tagName !== rest.toUpperCase()) return false;
  }
  return true;
}

function matchesComplexSelector(el: SimElement, selector: string): boolean {
  const parts = selector
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return false;
  if (!matchesSingleCompoundSelector(el, parts[parts.length - 1])) return false;
  let cur: SimElement | null = el.parentElement;
  for (let i = parts.length - 2; i >= 0; i -= 1) {
    while (cur && !matchesSingleCompoundSelector(cur, parts[i])) {
      cur = cur.parentElement;
    }
    if (!cur) return false;
    cur = cur.parentElement;
  }
  return true;
}

function matchesSelectorGroup(el: SimElement, groupSelector: string): boolean {
  const branches = groupSelector
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return branches.some((b) => matchesComplexSelector(el, b));
}

function queryElements(root: SimNode, selector: string, firstOnly: boolean): SimElement[] {
  const out: SimElement[] = [];
  walkElements(root, (el) => {
    if (matchesSelectorGroup(el, selector)) {
      out.push(el);
      if (firstOnly) return true;
    }
  });
  return out;
}

export const simDocument = new SimDocument();

export function resetDomBody(): SimElement {
  while (simDocument.body.childNodes.length > 0) {
    simDocument.body.removeChild(simDocument.body.childNodes[0]);
  }
  simDocument.activeElement = null;
  return simDocument.body;
}

export function installDomShim(): SimDocument {
  const g = globalThis as Record<string, unknown>;
  if (!g.document) {
    g.document = simDocument;
  }
  if (!g.Node) g.Node = SimNode;
  if (!g.Element) g.Element = SimElement;
  if (!g.HTMLElement) g.HTMLElement = SimElement;
  if (!g.HTMLInputElement) g.HTMLInputElement = SimHTMLInputElement;
  if (!g.HTMLTextAreaElement) g.HTMLTextAreaElement = SimHTMLTextAreaElement;
  if (!g.HTMLSelectElement) g.HTMLSelectElement = SimHTMLSelectElement;
  if (!g.HTMLOptionElement) g.HTMLOptionElement = SimHTMLOptionElement;
  if (!g.HTMLDialogElement) g.HTMLDialogElement = SimHTMLDialogElement;
  if (!g.HTMLTemplateElement) g.HTMLTemplateElement = SimHTMLTemplateElement;
  if (!g.DocumentFragment) g.DocumentFragment = SimDocumentFragment;
  if (!g.ShadowRoot) g.ShadowRoot = SimShadowRoot;
  if (!g.CSSStyleSheet) g.CSSStyleSheet = SimCSSStyleSheet;
  if (!g.CSS) {
    g.CSS = {
      escape(raw: string): string {
        return String(raw).replace(/[^A-Za-z0-9_-]/g, (ch) => `\\${ch}`);
      },
    };
  }
  if (!g.Event) g.Event = SimEvent;
  if (!g.CustomEvent) g.CustomEvent = SimCustomEvent;
  if (!g.KeyboardEvent) g.KeyboardEvent = SimKeyboardEvent;
  if (!g.FocusEvent) g.FocusEvent = SimFocusEvent;
  if (!g.MouseEvent) g.MouseEvent = SimMouseEvent;
  if (!g.customElements) g.customElements = simCustomElements;
  if (!g.requestAnimationFrame) {
    g.requestAnimationFrame = (cb: (ts: number) => void): number => {
      queueMicrotask(() => cb(Date.now()));
      return 1;
    };
  }
  if (!g.history) {
    g.history = {
      state: null,
      pushState(): void {},
      replaceState(): void {},
    };
  }
  if (!g.location) {
    g.location = { pathname: "/latter", search: "", hash: "", href: "http://localhost/latter" };
  }
  if (!g.dispatchEvent) {
    g.dispatchEvent = (ev: SimEvent): boolean => simDocument.dispatchEvent(ev);
  }
  if (!g.addEventListener) {
    g.addEventListener = (type: string, cb: Listener | null): void =>
      simDocument.addEventListener(type, cb);
  }
  if (!g.removeEventListener) {
    g.removeEventListener = (type: string, cb: Listener | null): void =>
      simDocument.removeEventListener(type, cb);
  }
  if (!g.window) {
    g.window = g;
  }
  return simDocument;
}

installDomShim();
