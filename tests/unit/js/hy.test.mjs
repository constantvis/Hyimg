// The primitives (review/ui/hy) in node: their pure rules (a badge's words, a chip's next state, an arrow key's step in a choice, a
// swatch's colour) and each element's state, attributes and hy- events on a small stand-in for HTMLElement. Layout, focus and the inner
// native controls are tested in the browsers (tests/test_primitives.py, Chromium and WebKit).
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { REPO } from "./load.mjs";

// a stand-in element: attributes with attributeChangedCallback, events kept in a list; nothing is in a document here
class FakeElement {
  constructor() { this._a = new Map(); this.events = []; this.style = { setProperty() {} }; this.children = []; this.textContent = ""; }
  get localName() { return this.constructor.tag || ""; }
  getAttribute(n) { return this._a.has(n) ? this._a.get(n) : null; }
  hasAttribute(n) { return this._a.has(n); }
  _changed(n, old, v) { if ((this.constructor.observedAttributes || []).includes(n)) this.attributeChangedCallback?.(n, old, v); }   // as a browser: observed ones only
  setAttribute(n, v) { const old = this.getAttribute(n); this._a.set(n, String(v)); this._changed(n, old, String(v)); }
  removeAttribute(n) { if (!this._a.has(n)) return; const old = this._a.get(n); this._a.delete(n); this._changed(n, old, null); }
  toggleAttribute(n, on) { if (on) this.setAttribute(n, ""); else this.removeAttribute(n); return !!on; }
  dispatchEvent(e) { this.events.push(e); return true; }
  closest() { return null; }
  querySelector() { return null; }
  focus() {}
}
const registry = new Map();
Object.assign(globalThis, {
  window: globalThis, HTMLElement: FakeElement,
  customElements: { get: t => registry.get(t), define: (t, c) => { if (registry.has(t)) throw new Error("defined twice: " + t); registry.set(t, c); c.tag = t; } },
  hySeg: () => {},   // the thumb's engine is the page's; segmented.js loads ui/seg.js only when there is none
});
const mod = f => import(pathToFileURL(path.join(REPO, "review/ui/hy", f)).href);
const HY = await mod("index.js");
const { badgeText } = await mod("badge.js"), { nextChipState } = await mod("chip.js"), { segStep } = await mod("segmented.js");
const { swatchColor } = await mod("swatch.js"), { define, oneOf } = await mod("base.js"), { BUTTON_PX, ICON_PX } = await mod("button.js");
const last = el => el.events[el.events.length - 1];

test("index.js defines every primitive once, under its tag", () => {
  const tags = ["hy-switch", "hy-check", "hy-kbd", "hy-badge", "hy-chip", "hy-hint", "hy-info", "hy-swatch", "hy-swatches", "hy-button",
    "hy-icon-button", "hy-plate", "hy-segmented", "hy-keyhint", "hy-tip", "hy-studio-actions", "hy-open-in", "hy-split",
    "hy-minitoggle", "hy-scope", "hy-led", "hy-scrub", "hy-stepper"];   // the micro controls (bf07b4b)
  assert.deepEqual([...registry.keys()].sort(), [...tags].sort());
  assert.equal(Object.values(HY).filter(c => c.tag).length, tags.length);   // classes only: scrub() is a helper beside its element
});

test("hy-keyhint: a combination's caps, and which key presses it (any layout, modifiers exact, a sign without ⇧)", async () => {
  const { caps, matches } = await mod("keyhint.js");
  assert.deepEqual(["shift+enter", "mod+b", "escape", "alt", "[", "-", "mod+enter"].map(caps), ["⇧↵", "⌘B", "Esc", "⌥", "[", "-", "⌘↵"]);
  const k = (key, o = {}) => ({ key, code: o.code || "", metaKey: !!o.meta, ctrlKey: false, shiftKey: !!o.shift, altKey: !!o.alt });
  assert.ok(matches("shift+enter", k("Enter", { shift: true })));
  assert.ok(!matches("shift+enter", k("Enter")) && !matches("enter", k("Enter", { shift: true })));   // Enter is not ⇧↵
  assert.ok(matches("mod+b", k("и", { meta: true, code: "KeyB" })));   // the Russian layout
  assert.ok(!matches("mod+b", k("b")));
  assert.ok(matches("@", k("@", { shift: true })) && matches("]", k("ъ", { code: "BracketRight" })));
  assert.ok(matches("alt", k("Alt", { alt: true })) && matches("escape", k("Escape")));
});

test("define() keeps the first class of a tag: a second import is harmless", () => {
  class Other extends FakeElement {}
  assert.equal(define("hy-button", Other), HY.HyButton);
  assert.equal(registry.get("hy-button"), HY.HyButton);
});

test("oneOf keeps a word from its list, else the default", () => {
  assert.equal(oneOf("solid", ["plain", "solid"], "plain"), "solid");
  assert.equal(oneOf("xl", ["plain", "solid"], "plain"), "plain");
  assert.equal(oneOf(null, ["s", "m"], "m"), "m");
});

test("hy-switch: checked is its attribute, toggle() sends hy-change once per change, disabled holds it", () => {
  const s = new HY.HySwitch();
  assert.equal(s.checked, false);
  s.toggle(); assert.equal(s.checked, true); assert.equal(s.getAttribute("checked"), "");
  assert.equal(last(s).type, "hy-change"); assert.deepEqual(last(s).detail, { checked: true });
  s.toggle(true); assert.equal(s.events.length, 1, "no change, no event");
  s.disabled = true; s.toggle(); assert.equal(s.checked, true);
  s.checked = false; assert.equal(s.hasAttribute("checked"), false);
});

test("hy-check: checked and indeterminate are attributes", () => {
  const c = new HY.HyCheck();
  c.indeterminate = true; assert.ok(c.hasAttribute("indeterminate"));
  c.checked = true; c.indeterminate = false; assert.ok(c.checked); assert.ok(!c.hasAttribute("indeterminate"));
});

test("hy-kbd: three sizes, l by default and never written", () => {
  const k = new HY.HyKbd();
  assert.equal(k.size, "l"); k.size = "s"; assert.equal(k.getAttribute("size"), "s"); k.size = "l"; assert.equal(k.hasAttribute("size"), false);
});

test("hy-badge: a count's words, 99+ above 99, nothing for no number", () => {
  assert.equal(badgeText("3"), "3"); assert.equal(badgeText("120"), "99+"); assert.equal(badgeText(""), ""); assert.equal(badgeText("x"), "");
  assert.equal(badgeText(null), ""); assert.equal(badgeText("-2"), "0");
  const b = new HY.HyBadge(); b.count = 7; assert.equal(b.textContent, "7");
  b.setAttribute("label", "7 new"); assert.equal(b.getAttribute("role"), "status"); assert.equal(b.getAttribute("aria-label"), "7 new");
  assert.equal(b.tone, "sel"); b.tone = "red"; assert.equal(b.getAttribute("tone"), "red");
});

test("hy-chip: off → include → exclude → off, or off ↔ include with cycle=two; hy-change says the state", () => {
  assert.equal(nextChipState("off", false), "include"); assert.equal(nextChipState("include", false), "exclude");
  assert.equal(nextChipState("exclude", false), "off"); assert.equal(nextChipState("include", true), "off");
  const c = new HY.HyChip();
  c.press(); assert.equal(c.state, "include"); assert.deepEqual(last(c).detail, { state: "include" });
  c.press(); c.press(); assert.equal(c.state, "off"); assert.equal(c.hasAttribute("state"), false);
  c.setAttribute("disabled", ""); c.press(); assert.equal(c.state, "off");
});

test("hy-info: its tip is what it explains", () => {
  const i = new HY.HyInfo(); i.tip = "Opens the frame"; assert.equal(i.getAttribute("tip"), "Opens the frame"); i.tip = ""; assert.equal(i.hasAttribute("tip"), false);
});

test("hy-swatch: a token's name becomes var(), a value stays; alone it toggles", () => {
  assert.equal(swatchColor("--hy-sel"), "var(--hy-sel)"); assert.equal(swatchColor("#f4c430"), "#f4c430"); assert.equal(swatchColor(null), "");
  const s = new HY.HySwatch(); s.setAttribute("color", "#f4c430");
  assert.equal(s.value, "#f4c430");
  s.pick(); assert.ok(s.selected); assert.deepEqual(last(s).detail, { selected: true, value: "#f4c430" });
  const n = new HY.HySwatch(); n.setAttribute("none", ""); assert.equal(n.value, "");
});

test("hy-button and hy-icon-button: variants and sizes are words of their lists, sizes are the scale's heights", () => {
  const b = new HY.HyButton();
  assert.equal(b.variant, "plain"); assert.equal(b.size, "m");
  b.variant = "solid"; assert.equal(b.getAttribute("variant"), "solid");
  b.size = "plate"; assert.equal(b.getAttribute("size"), "plate"); b.size = "m"; assert.equal(b.hasAttribute("size"), false);
  b.pressed = true; assert.ok(b.hasAttribute("pressed"));
  assert.deepEqual(BUTTON_PX, { xs: 20, s: 24, m: 28, l: 30, row: 32, dock: 34, plate: 38 });
  for (const k of Object.keys(BUTTON_PX)) assert.ok(ICON_PX[k] < BUTTON_PX[k], k);
  const i = new HY.HyIconButton(); assert.equal(i.variant, "ghost");
});

test("hy-plate: a title by default, capsule when asked", () => {
  const p = new HY.HyPlate(); assert.equal(p.kind, "title"); p.kind = "capsule"; assert.equal(p.getAttribute("kind"), "capsule");
});

test("hy-segmented: an arrow key goes round the ends, Home and End to the ends, other keys stay", () => {
  assert.equal(segStep("ArrowRight", 2, 3), 0); assert.equal(segStep("ArrowLeft", 0, 3), 2); assert.equal(segStep("ArrowDown", 0, 3), 1);
  assert.equal(segStep("Home", 2, 3), 0); assert.equal(segStep("End", 0, 3), 2); assert.equal(segStep("a", 1, 3), -1); assert.equal(segStep("ArrowRight", 0, 0), -1);
  const s = new HY.HySegmented(); s.value = "b"; assert.equal(s.value, "b"); assert.equal(s.variant, "choice");
});
