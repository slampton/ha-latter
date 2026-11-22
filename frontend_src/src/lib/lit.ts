/**
 * Stock `lit` (v3.3.3, BSD-3-Clause) re-exports, `focusSafe` property directive (`D-039`),
 * `live` directive, and duplicate-key-safe `repeat` directive (`D-062`, `D-078`).
 */

import {
  css,
  html,
  LitElement,
  noChange,
  nothing,
  render,
  svg,
  type CSSResult,
  type CSSResultGroup,
  type HTMLTemplateResult,
  type PropertyValues,
  type ReactiveController,
  type ReactiveControllerHost,
  type RenderOptions,
  type RootPart,
  type SVGTemplateResult,
  type TemplateResult,
} from "lit";
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
} from "lit/directive.js";
import { live } from "lit/directives/live.js";
import {
  repeat as litRepeat,
  type ItemTemplate,
  type KeyFn,
} from "lit/directives/repeat.js";

export {
  css,
  Directive,
  directive,
  html,
  LitElement,
  live,
  noChange,
  nothing,
  PartType,
  render,
  svg,
  type AttributePart,
  type BooleanAttributePart,
  type ChildPart,
  type CSSResult,
  type CSSResultGroup,
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
  type PropertyValues,
  type ReactiveController,
  type ReactiveControllerHost,
  type RenderOptions,
  type RootPart,
  type SVGTemplateResult,
  type TemplateResult,
};

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
