/**
 * Vendored `lit-html` (v3.3.3, BSD-3-Clause) wrapper, thin `LitElement` reactive host,
 * `focusSafe` property directive (`D-039`), and duplicate-key-safe `repeat` directive (`D-062`).
 */

import {
  Directive,
  directive,
  PartType,
  type AttributePart,
  type BooleanAttributePart,
  type ChildPart,
  type DirectiveClass,
  type DirectiveResult,
  type ElementPart,
  type EventPart,
  type Part,
  type PartInfo,
  type PropertyPart,
} from "./vendor/directive.js";
import {
  repeat as litRepeat,
  type ItemTemplate,
  type KeyFn,
} from "./vendor/directives/repeat.js";
import {
  html,
  noChange,
  nothing,
  render,
  svg,
  type HTMLTemplateResult,
  type RenderOptions,
  type RenderRootNode,
  type RootPart,
  type SVGTemplateResult,
  type TemplateResult,
} from "./vendor/lit-html.js";

export {
  Directive,
  directive,
  html,
  noChange,
  nothing,
  PartType,
  render,
  svg,
  type AttributePart,
  type BooleanAttributePart,
  type ChildPart,
  type DirectiveClass,
  type DirectiveResult,
  type ElementPart,
  type EventPart,
  type HTMLTemplateResult,
  type ItemTemplate,
  type KeyFn,
  type Part,
  type PartInfo,
  type PropertyPart,
  type RenderOptions,
  type RenderRootNode,
  type RootPart,
  type SVGTemplateResult,
  type TemplateResult,
};

export type KeyedResult = unknown;

export interface CSSResult {
  readonly styleSheetText: string;
}

const STYLE_SHEET_CACHE = new WeakMap<CSSResult, CSSStyleSheet>();

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

function getCachedStyleSheet(res: CSSResult): CSSStyleSheet {
  let sheet = STYLE_SHEET_CACHE.get(res);
  if (!sheet) {
    sheet = new CSSStyleSheet();
    sheet.replaceSync(res.styleSheetText);
    STYLE_SHEET_CACHE.set(res, sheet);
  }
  return sheet;
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

const NON_TEXT_INPUT_TYPES = new Set([
  "button",
  "checkbox",
  "color",
  "file",
  "hidden",
  "image",
  "radio",
  "range",
  "reset",
  "submit",
]);

export function isActivelyFocusedTextControl(el: Element | null | undefined): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag !== "INPUT" && tag !== "TEXTAREA") return false;
  if (tag === "INPUT") {
    const inpType = ((el as HTMLInputElement).type || "text").toLowerCase();
    if (NON_TEXT_INPUT_TYPES.has(inpType)) return false;
  }
  const root = typeof el.getRootNode === "function" ? el.getRootNode() : null;
  if (root && typeof root === "object" && "activeElement" in root) {
    return (root as Document | ShadowRoot).activeElement === el;
  }
  return typeof document !== "undefined" && document.activeElement === el;
}

class FocusSafeDirective extends Directive {
  private _initialized = false;

  constructor(partInfo: PartInfo) {
    super(partInfo);
    if (partInfo.type !== PartType.PROPERTY && partInfo.type !== PartType.ATTRIBUTE) {
      throw new Error("focusSafe() can only be used in property or attribute bindings");
    }
  }

  render(value: unknown): unknown {
    return value === nothing || value === null || value === undefined ? "" : value;
  }

  override update(part: Part, [value]: [unknown]): unknown {
    const normalized = value === nothing || value === null || value === undefined ? "" : value;
    if (this._initialized && "element" in part && isActivelyFocusedTextControl(part.element)) {
      return noChange;
    }
    this._initialized = true;
    if ("element" in part && part.type === PartType.PROPERTY) {
      const target = part.element as unknown as Record<string, unknown>;
      if (target[part.name] !== normalized) {
        target[part.name] = normalized;
      }
      return noChange;
    }
    return normalized;
  }
}

/**
 * Property directive (`D-039`) that prevents background reactive updates from clobbering `.value`
 * on an actively focused `<input>` or `<textarea>`, while syncing live DOM value once blurred.
 */
export const focusSafe = directive(FocusSafeDirective);

/**
 * Keyed `repeat()` directive with an automatic duplicate-key guard so accidental colliding keys
 * never crash or orphan DOM nodes.
 */
export function repeat<T>(items: Iterable<T>, template: ItemTemplate<T>): unknown;
export function repeat<T>(
  items: Iterable<T>,
  keyFn: KeyFn<T>,
  template: ItemTemplate<T>,
): unknown;
export function repeat<T>(
  items: Iterable<T>,
  keyFnOrTemplate: KeyFn<T> | ItemTemplate<T>,
  template?: ItemTemplate<T>,
): unknown {
  if (template === undefined) {
    return litRepeat(items, keyFnOrTemplate as ItemTemplate<T>);
  }
  const keyFn = keyFnOrTemplate as KeyFn<T>;
  const seenKeys = new Map<unknown, number>();
  const safeKeyFn: KeyFn<T> = (item, index) => {
    if (index === 0) {
      seenKeys.clear();
    }
    const rawKey = keyFn(item, index);
    const prevCount = seenKeys.get(rawKey) ?? 0;
    seenKeys.set(rawKey, prevCount + 1);
    if (prevCount === 0) {
      return rawKey;
    }
    return `${String(rawKey)}__dup_${prevCount}`;
  };
  return litRepeat(items, safeKeyFn, template);
}

const BaseHTMLElement: typeof HTMLElement =
  typeof HTMLElement !== "undefined"
    ? HTMLElement
    : (class {} as unknown as typeof HTMLElement);

export class LitElement extends BaseHTMLElement implements ReactiveControllerHost {
  static styles?: CSSResult | readonly CSSResult[];

  readonly renderRoot: ShadowRoot;
  private readonly _controllers = new Set<ReactiveController>();
  private _updatePending = false;
  private _hasUpdated = false;
  private _updatePromise: Promise<boolean> = Promise.resolve(true);
  private _rootPart: RootPart | null = null;
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
    this._rootPart?.setConnected(true);
    for (const c of this._controllers) {
      c.hostConnected?.();
    }
    this.requestUpdate();
  }

  disconnectedCallback(): void {
    for (const c of this._controllers) {
      c.hostDisconnected?.();
    }
    this._rootPart?.setConnected(false);
  }

  get updateComplete(): Promise<boolean> {
    return this._updatePromise;
  }

  requestUpdate(): void {
    if (this._updatePending) return;
    this._updatePending = true;
    let resolveCycle!: (val: boolean) => void;
    this._updatePromise = new Promise<boolean>((resolve) => {
      resolveCycle = resolve;
    });
    queueMicrotask(() => this._performUpdate(resolveCycle));
  }

  private _adoptStylesOnce(): void {
    if (this._stylesAdopted) return;
    this._stylesAdopted = true;
    const ctor = this.constructor as typeof LitElement;
    if (!ctor.styles) return;
    const list = Array.isArray(ctor.styles) ? ctor.styles : [ctor.styles];
    if (typeof CSSStyleSheet !== "undefined" && "adoptedStyleSheets" in this.renderRoot) {
      this.renderRoot.adoptedStyleSheets = list.map((s) => getCachedStyleSheet(s));
    }
  }

  private _performUpdate(resolveCycle: (val: boolean) => void): void {
    this._updatePending = false;
    if (!this.isConnected) {
      resolveCycle(false);
      return;
    }
    let completed = false;
    try {
      this._adoptStylesOnce();
      for (const c of this._controllers) {
        c.hostUpdate?.();
      }
      const rendered = this.render();
      this._rootPart = render(rendered, this.renderRoot, { host: this });
      if (!this._hasUpdated) {
        this._hasUpdated = true;
        this.firstUpdated();
      }
      this.updated();
      for (const c of this._controllers) {
        c.hostUpdated?.();
      }
      completed = true;
    } catch (err) {
      console.error("[latter-studio] Render update failed:", err);
    } finally {
      resolveCycle(completed);
    }
  }

  protected render(): unknown {
    return nothing;
  }

  protected firstUpdated(): void {}

  protected updated(): void {}
}
