/**
 * Frontend DOM & unit tests for `src/lib/lit.ts` (`D-039`, `D-062`, `A-01`, `A-03`, `U5`):
 * - `LitElement` lifecycle & `ReactiveController` callbacks
 * - `WeakMap<CSSResult, CSSStyleSheet>` `adoptedStyleSheets` caching
 * - Per-cycle `updateComplete` resolution when `requestUpdate()` fires inside `updated()`
 * - `repeat()` duplicate-key guard (`A-01`)
 * - Mixed nested array rendering (`A-03`)
 * - `focusSafe()` active focus preservation on `<input>` and `<textarea>` (`D-039`)
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import {
  css,
  focusSafe,
  html,
  isActivelyFocusedTextControl,
  LitElement,
  nothing,
  render,
  repeat,
  type ReactiveController,
} from "../src/lib/lit.js";
import { resetDomBody, simDocument } from "./dom-shim.js";

const SHARED_SHEET_A = css`
  :host {
    --test-fg: #123456;
    --test-size: 14px;
  }
  .box {
    color: var(--test-fg);
    font-size:var(--test-size);
  }
`;

const SHARED_SHEET_B = css`
  :host {
    --test-pad: 8px;
  }
  .pad {
    padding: var(--test-pad);
  }
`;

describe("src/lib/lit.ts — LitElement, repeat(), nested arrays & focusSafe()", () => {
  beforeEach(() => {
    resetDomBody();
  });

  it("drives LitElement lifecycle & ReactiveController callbacks cleanly", async () => {
    const log: string[] = [];

    class LifecycleHost extends LitElement {
      count = 0;

      protected override render(): unknown {
        log.push(`render:${this.count}`);
        return html`<span id="val">${this.count}</span>`;
      }

      protected override firstUpdated(): void {
        log.push("firstUpdated");
      }

      protected override updated(): void {
        log.push(`updated:${this.count}`);
      }
    }
    customElements.define("test-lifecycle-host", LifecycleHost);

    const ctrl: ReactiveController = {
      hostConnected: () => log.push("ctrl:connected"),
      hostUpdate: () => log.push("ctrl:update"),
      hostUpdated: () => log.push("ctrl:updated"),
      hostDisconnected: () => log.push("ctrl:disconnected"),
    };

    const el = simDocument.createElement("test-lifecycle-host") as unknown as LifecycleHost;
    el.addController(ctrl);
    simDocument.body.appendChild(el as unknown as Parameters<typeof simDocument.body.appendChild>[0]);

    const firstOk = await el.updateComplete;
    assert.equal(firstOk, true);
    assert.equal(el.renderRoot.getElementById("val")?.textContent, "0");
    assert.deepEqual(log, [
      "ctrl:connected",
      "ctrl:update",
      "render:0",
      "firstUpdated",
      "updated:0",
      "ctrl:updated",
    ]);

    log.length = 0;
    el.count = 1;
    el.requestUpdate();
    await el.updateComplete;
    assert.equal(el.renderRoot.getElementById("val")?.textContent, "1");
    assert.deepEqual(log, ["ctrl:update", "render:1", "updated:1", "ctrl:updated"]);

    log.length = 0;
    (el as unknown as { remove: () => void }).remove();
    assert.deepEqual(log, ["ctrl:disconnected"]);
  });

  it("caches CSSStyleSheet instances in a WeakMap across LitElement instances", async () => {
    class StyledCard extends LitElement {
      static override styles = [SHARED_SHEET_A, SHARED_SHEET_B];
      protected override render(): unknown {
        return html`<div class="box pad">Styled</div>`;
      }
    }
    customElements.define("test-styled-card", StyledCard);

    const cardA = simDocument.createElement("test-styled-card") as unknown as StyledCard;
    const cardB = simDocument.createElement("test-styled-card") as unknown as StyledCard;
    simDocument.body.appendChild(cardA as unknown as Parameters<typeof simDocument.body.appendChild>[0]);
    simDocument.body.appendChild(cardB as unknown as Parameters<typeof simDocument.body.appendChild>[0]);
    await Promise.all([cardA.updateComplete, cardB.updateComplete]);

    assert.equal(cardA.renderRoot.adoptedStyleSheets.length, 2);
    assert.equal(cardB.renderRoot.adoptedStyleSheets.length, 2);
    assert.strictEqual(
      cardA.renderRoot.adoptedStyleSheets[0],
      cardB.renderRoot.adoptedStyleSheets[0],
    );
    assert.strictEqual(
      cardA.renderRoot.adoptedStyleSheets[1],
      cardB.renderRoot.adoptedStyleSheets[1],
    );
    assert.notStrictEqual(
      cardA.renderRoot.adoptedStyleSheets[0],
      cardA.renderRoot.adoptedStyleSheets[1],
    );
  });

  it("resolves each cycle's updateComplete independently when requestUpdate() fires inside updated()", async () => {
    const events: string[] = [];
    let cycle2Promise: Promise<boolean> | null = null;

    class ChainedUpdateElement extends LitElement {
      step = 1;

      protected override render(): unknown {
        events.push(`render:${this.step}`);
        return html`<p id="step">${this.step}</p>`;
      }

      protected override updated(): void {
        events.push(`updated:${this.step}`);
        if (this.step === 1) {
          this.step = 2;
          this.requestUpdate();
          cycle2Promise = this.updateComplete;
        }
      }
    }
    customElements.define("test-chained-update", ChainedUpdateElement);

    const el = simDocument.createElement("test-chained-update") as unknown as ChainedUpdateElement;
    simDocument.body.appendChild(el as unknown as Parameters<typeof simDocument.body.appendChild>[0]);

    const cycle1Promise = el.updateComplete;
    const res1 = await cycle1Promise;
    assert.equal(res1, true);
    assert.notStrictEqual(cycle1Promise, cycle2Promise);
    assert.ok(cycle2Promise !== null);

    const res2 = await cycle2Promise;
    assert.equal(res2, true);
    assert.equal(el.renderRoot.getElementById("step")?.textContent, "2");
    assert.deepEqual(events, ["render:1", "updated:1", "render:2", "updated:2"]);
  });

  it("resolves updateComplete cleanly on disconnected hosts and render errors", async () => {
    class DetachedAndFaulty extends LitElement {
      shouldThrow = false;
      protected override render(): unknown {
        if (this.shouldThrow) {
          throw new Error("boom");
        }
        return html`<div>ok</div>`;
      }
    }
    customElements.define("test-detached-faulty", DetachedAndFaulty);

    const detached = simDocument.createElement("test-detached-faulty") as unknown as DetachedAndFaulty;
    detached.requestUpdate();
    assert.equal(await detached.updateComplete, false);

    simDocument.body.appendChild(detached as unknown as Parameters<typeof simDocument.body.appendChild>[0]);
    assert.equal(await detached.updateComplete, true);

    const origErr = console.error;
    console.error = () => {};
    try {
      detached.shouldThrow = true;
      detached.requestUpdate();
      assert.equal(await detached.updateComplete, false);
    } finally {
      console.error = origErr;
    }
  });

  it("guards repeat() against duplicate keys without crashing or orphaning DOM nodes (A-01)", () => {
    const container = simDocument.createElement("div");

    const renderList = (items: ReadonlyArray<{ id: string; label: string }>): void => {
      render(
        html`<ul>
          ${repeat(
            items,
            (item) => item.id,
            (item) => html`<li data-id=${item.id}>${item.label}</li>`,
          )}
        </ul>`,
        container,
      );
    };

    renderList([
      { id: "dup", label: "First" },
      { id: "dup", label: "Second" },
      { id: "uniq", label: "Third" },
      { id: "dup", label: "Fourth" },
    ]);
    assert.deepEqual(
      container.querySelectorAll("li").map((li) => li.textContent),
      ["First", "Second", "Third", "Fourth"],
    );

    // Reorder & shrink with duplicates still present — zero orphaned nodes
    renderList([
      { id: "uniq", label: "Third Updated" },
      { id: "dup", label: "Only Dup Left" },
    ]);
    assert.deepEqual(
      container.querySelectorAll("li").map((li) => li.textContent),
      ["Third Updated", "Only Dup Left"],
    );

    // Unkeyed 2-argument repeat() overload
    render(
      html`<ol>${repeat(["x", "y"], (v, idx) => html`<li>${idx}:${v}</li>`)}</ol>`,
      container,
    );
    assert.deepEqual(
      container.querySelectorAll("li").map((li) => li.textContent),
      ["0:x", "1:y"],
    );
  });

  it("renders and updates mixed nested arrays cleanly (A-03)", () => {
    const container = simDocument.createElement("div");

    const tpl = (showExtra: boolean) => html`<section>
      ${[
        "Alpha",
        nothing,
        [
          html`<em>Beta</em>`,
          showExtra ? [42, html`<strong>Gamma</strong>`] : nothing,
        ],
        repeat(
          ["one", "two"],
          (k) => k,
          (k) => html`<span class="item">${k}</span>`,
        ),
      ]}
    </section>`;

    render(tpl(true), container);
    assert.equal(container.querySelector("em")?.textContent, "Beta");
    assert.equal(container.querySelector("strong")?.textContent, "Gamma");
    assert.deepEqual(
      container.querySelectorAll(".item").map((n) => n.textContent),
      ["one", "two"],
    );
    assert.ok(container.textContent.includes("Alpha"));
    assert.ok(container.textContent.includes("42"));

    render(tpl(false), container);
    assert.equal(container.querySelector("strong"), null);
    assert.ok(!container.textContent.includes("42"));
    assert.deepEqual(
      container.querySelectorAll(".item").map((n) => n.textContent),
      ["one", "two"],
    );
  });

  it("skips overwriting actively focused <input> and <textarea> values via focusSafe() (D-039)", async () => {
    class FocusHost extends LitElement {
      textVal = "Initial";
      notesVal = "Notes 1";
      rangeVal = "40";

      protected override render(): unknown {
        return html`
          <input id="txt" type="text" .value=${focusSafe(this.textVal)} />
          <textarea id="area" .value=${focusSafe(this.notesVal)}></textarea>
          <input id="rng" type="range" .value=${focusSafe(this.rangeVal)} />
        `;
      }
    }
    customElements.define("test-focus-host", FocusHost);

    const host = simDocument.createElement("test-focus-host") as unknown as FocusHost;
    simDocument.body.appendChild(host as unknown as Parameters<typeof simDocument.body.appendChild>[0]);
    await host.updateComplete;

    const txt = host.renderRoot.getElementById("txt") as unknown as HTMLInputElement;
    const area = host.renderRoot.getElementById("area") as unknown as HTMLTextAreaElement;
    const rng = host.renderRoot.getElementById("rng") as unknown as HTMLInputElement;

    assert.equal(txt.value, "Initial");
    assert.equal(area.value, "Notes 1");
    assert.equal(rng.value, "40");

    // Focus `<input type="text">` and simulate user mid-typing with trailing space
    txt.focus();
    assert.equal(isActivelyFocusedTextControl(txt as unknown as Element), true);
    txt.value = "User typing ";

    host.textVal = "Server clobber attempt";
    host.notesVal = "Server notes 2";
    host.requestUpdate();
    await host.updateComplete;

    // Focused text input keeps user typing; unfocused textarea updates immediately!
    assert.equal(txt.value, "User typing ");
    assert.equal(area.value, "Server notes 2");

    // Blur text input and focus textarea -> text input syncs on next update, textarea stays protected
    txt.blur();
    area.focus();
    area.value = "Drafting area...";
    host.textVal = "Synced after blur";
    host.notesVal = "Server notes 3";
    host.requestUpdate();
    await host.updateComplete;

    assert.equal(txt.value, "Synced after blur");
    assert.equal(area.value, "Drafting area...");

    // Non-text `<input type="range">` always updates even when focused
    area.blur();
    rng.focus();
    assert.equal(isActivelyFocusedTextControl(rng as unknown as Element), false);
    host.rangeVal = "85";
    host.requestUpdate();
    await host.updateComplete;
    assert.equal(rng.value, "85");

    // Invalid child-part usage throws cleanly
    const badContainer = simDocument.createElement("div");
    assert.throws(
      () => render(html`<div>${focusSafe("bad")}</div>`, badContainer),
      /focusSafe\(\) can only be used in property or attribute bindings/,
    );
  });
});
