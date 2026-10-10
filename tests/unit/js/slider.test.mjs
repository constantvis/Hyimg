// ui/slider.js: the value and position math of the app's one slider, driven by pointer and key events on the fake DOM
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

// a slider 200 px wide at the window's left edge
function slider(o = {}, attrs = {}) {
  const p = page({ scripts: ["ui/slider.js"] });
  const s = p.window.hySlider.create(Object.assign({ label: "Lens", value: 70, min: 0, max: 100, step: 1 }, o));
  for (const [k, v] of Object.entries(attrs)) s.el.dataset[k] = v;
  s.el._rect = { left: 0, top: 0, width: 200, height: 24 };
  p.document.body.appendChild(s.el); s.paint();
  const events = [];
  s.input.addEventListener("input", () => events.push(["input", +s.input.value]));
  s.input.addEventListener("change", () => events.push(["change", +s.input.value]));
  // a move during a drag has the button down (buttons 1), as the browser says it; a test that lets go elsewhere passes buttons: 0
  const at = (type, x, mods = {}) => p.fire(s.el, type, Object.assign({ clientX: x, clientY: 10, buttons: type === "pointermove" ? 1 : 0 }, mods));
  const drag = (from, to, mods = {}) => { at("pointerdown", from); at("pointermove", from + 5); at("pointermove", to, mods); at("pointerup", to, mods); };
  return { p, s, events, at, drag, v: () => +s.input.value, P: () => +s.el.style.getPropertyValue("--p") };
}

test("a new slider paints its fill at the value's share of the range and writes the number with its unit", () => {
  const { s, P } = slider({ value: 30, unit: "%" });
  assert.equal(P(), 0.3);
  assert.equal(s.el.querySelector(".hy-slider-v").textContent, "30%");
  assert.equal(s.input.getAttribute("aria-valuetext"), "30%");
});

test("a slider dragged past its end stays at its maximum", () => {
  const { drag, v, P } = slider();
  drag(100, 5000);
  assert.equal(v(), 100);
  assert.equal(P(), 1);
});

test("a slider dragged before its start stays at its minimum", () => {
  const { drag, v } = slider();
  drag(100, -5000);
  assert.equal(v(), 0);
});

test("a drag moves the value from where it was grabbed, it does not jump to the pointer", () => {
  const { at, v } = slider({ value: 70 });
  at("pointerdown", 10);   // far left of the value's place (140 px)
  at("pointermove", 20);   // 10 px right: 5 % of 200 px
  assert.equal(v(), 75);
});

test("a press that moves 3 px or less is a click, not a drag", () => {
  const { at, v } = slider({ value: 70 });
  at("pointerdown", 100); at("pointermove", 102);
  assert.equal(v(), 70);
});

test("shift makes a drag ten times finer and alt a hundred times", () => {
  const a = slider({ value: 50 });
  a.at("pointerdown", 100); a.at("pointermove", 105, { shiftKey: true }); a.at("pointermove", 145, { shiftKey: true });   // 40 px: 20 % of the range, a tenth of it
  assert.equal(a.v(), 52);
  const b = slider({ value: 50 });
  b.at("pointerdown", 100); b.at("pointermove", 105, { altKey: true }); b.at("pointermove", 305, { altKey: true });     // 200 px: the whole range, a hundredth of it
  assert.equal(b.v(), 51);
});

test("a modifier pressed in the middle of a drag goes on from the value reached, without a jump", () => {
  const { at, v } = slider({ value: 50 });
  at("pointerdown", 100); at("pointermove", 105); at("pointermove", 120);   // +20 px: 60
  assert.equal(v(), 60);
  at("pointermove", 120, { shiftKey: true });   // shift pressed where the pointer stands: nothing moves
  assert.equal(v(), 60);
  at("pointermove", 140, { shiftKey: true });   // +20 px at a tenth: +1
  assert.equal(v(), 61);
});

test("a click without a drag puts the value where the pointer is", () => {
  const { at, v, events } = slider({ value: 70 });
  at("pointerdown", 50); at("pointerup", 50);
  assert.equal(v(), 25);
  assert.deepEqual(events, [["input", 25], ["change", 25]]);
});

test("a click close to a tenth of a long range lands on that tenth", () => {
  const { at, v } = slider({ value: 70 });
  at("pointerdown", 58); at("pointerup", 58);   // 29 %: within 1/32 of 30 %
  assert.equal(v(), 30);
});

test("a click on a short range lands on the nearest step, not on a tenth", () => {
  const { at, v } = slider({ value: 2, min: 0, max: 5, step: 1 });
  at("pointerdown", 58); at("pointerup", 58);   // 29 % of 0..5 = 1.45
  assert.equal(v(), 1);
});

test("a drag ends with one change event after its input events", () => {
  const { drag, events } = slider({ value: 50 });
  drag(100, 140);
  assert.equal(events.filter(e => e[0] === "change").length, 1);
  assert.equal(events.at(-1)[0], "change");
  assert.ok(events.slice(0, -1).every(e => e[0] === "input"));
});

test("a drag let go where the slider never heard it ends at the next move without a button: a hover moves nothing", () => {
  const { at, s, events } = slider({ value: 50 });
  at("pointerdown", 100); at("pointermove", 105); at("pointermove", 120);   // +20 px: 60
  assert.equal(+s.input.value, 60);
  at("pointermove", 160, { buttons: 0 });   // the pointerup went to a live page's frame (owner 2026-10-10, Dev Studio's Opacity)
  at("pointermove", 20, { buttons: 0 }); at("pointermove", 200, { buttons: 0 });
  assert.equal(+s.input.value, 60);
  assert.equal(events.filter(e => e[0] === "change").length, 1, "what the drag moved is kept as one change");
});

test("values on a fractional step come out on the step grid without float noise", () => {
  const { drag, v, s } = slider({ value: 0.5, min: 0, max: 1, step: 0.05 });
  drag(100, 131);   // +31 px of 200: +0.155, snapped to 0.65
  assert.equal(v(), 0.65);
  assert.equal(String(s.input.value), "0.65");
  assert.equal(s.el.querySelector(".hy-slider-v").textContent, "0.65");
});

test("the number shows as many decimals as the step has, an exponent step included", () => {
  assert.equal(slider({ value: 0.5, min: 0, max: 1, step: 0.01 }).s.el.querySelector(".hy-slider-v").textContent, "0.50");
  assert.equal(slider({ value: 0.5, min: 0, max: 1, step: "1e-3" }).s.el.querySelector(".hy-slider-v").textContent, "0.500");
  assert.equal(slider({ value: 7, min: 0, max: 10, step: 1 }).s.el.querySelector(".hy-slider-v").textContent, "7");
});

test("set() snaps a value to the step and clamps it to the range", () => {
  const { s, v } = slider({ value: 0, min: 0, max: 10, step: 2 });
  s.set(5.2); assert.equal(v(), 6);
  s.set(99); assert.equal(v(), 10);
  s.set(-3); assert.equal(v(), 0);
});

test("a step that does not divide the range still reaches its maximum", () => {
  const { drag, v } = slider({ value: 0, min: 0, max: 10, step: 3 });
  drag(0, 400);
  assert.equal(v(), 10);
});

test("a slider whose max is not above its min paints as a range of 1, not a division by zero", () => {
  const { P } = slider({ value: 5, min: 5, max: 5 });
  assert.equal(P(), 0);
});

test("a sqrt curve paints the fill at the square root of the share", () => {
  const { p } = slider();
  const s = p.window.hySlider.create({ value: 25, min: 0, max: 100 });
  s.el.dataset.curve = "sqrt"; s.paint();
  assert.equal(+s.el.style.getPropertyValue("--p"), 0.5);
});

test("a signed slider fills from its centre to the value on either side", () => {
  const { s } = slider({ value: 25, min: -100, max: 100 }, { center: "0" });
  s.paint();
  const g = k => +s.el.style.getPropertyValue(k);
  assert.equal(g("--c"), 0.5); assert.equal(g("--p"), 0.625);
  assert.equal(g("--fl"), 0.5); assert.equal(g("--fw"), 0.125);
  s.set(-50);
  assert.equal(g("--fl"), 0.25); assert.equal(g("--fw"), 0.25);
});

test("shift and an arrow move ten steps, clamped at the end", () => {
  const { p, s, v } = slider({ value: 95 });
  p.fire(s.input, "keydown", { key: "ArrowRight", shiftKey: true });
  assert.equal(v(), 100);
  p.fire(s.input, "keydown", { key: "ArrowDown", shiftKey: true });
  assert.equal(v(), 90);
});

test("an arrow without shift is left to the native range", () => {
  const { p, s, v } = slider({ value: 50 });
  const e = p.fire(s.input, "keydown", { key: "ArrowRight" });
  assert.equal(v(), 50);
  assert.equal(e.defaultPrevented, false);
});

test("a double click puts back the slider's default when it has one", () => {
  const { p, s, v, events } = slider({ value: 70 }, { reset: "20" });
  p.fire(s.el, "dblclick");
  assert.equal(v(), 20);
  assert.deepEqual(events, [["input", 20], ["change", 20]]);
});

// the number field: a click on the number types the value
function typeInto(t, text, key = "Enter") {
  const out = t.s.el.querySelector(".hy-slider-v");
  t.p.fire(out, "click");
  const f = t.s.el.querySelector(".hy-slider-ed");
  assert.ok(f, "the field opens");
  assert.equal(out.hidden, true);
  f.value = text;
  t.p.fire(f, "keydown", { key });
  return { out, f };
}

test("a typed number sets the value, a comma read as a decimal point", () => {
  const t = slider({ value: 1, min: 0, max: 10, step: 0.5 });
  const { out } = typeInto(t, "4,5");
  assert.equal(t.v(), 4.5);
  assert.equal(out.hidden, false);
  assert.equal(t.s.el.querySelector(".hy-slider-ed"), null);
  assert.deepEqual(t.events, [["input", 4.5], ["change", 4.5]]);
});

test("a typed number out of the range is clamped to it", () => {
  const t = slider({ value: 1 });
  typeInto(t, "250");
  assert.equal(t.v(), 100);
});

test("escape leaves the typed number unused", () => {
  const t = slider({ value: 30 });
  typeInto(t, "80", "Escape");
  assert.equal(t.v(), 30);
  assert.deepEqual(t.events, []);
});

test("text that is no number leaves the value as it was", () => {
  const t = slider({ value: 30 });
  typeInto(t, "abc");
  assert.equal(t.v(), 30);
  assert.deepEqual(t.events, []);
});

test("a host's parse() decides what typed text means", () => {
  const t = slider({ value: 30 });
  t.s.parse = (text, cur) => (text.startsWith("+") ? cur + Number(text.slice(1)) : Number(text));
  typeInto(t, "+15");
  assert.equal(t.v(), 45);
});

test("a disabled slider ignores the pointer", () => {
  const t = slider({ value: 30 });
  t.s.input.disabled = true;
  t.at("pointerdown", 150); t.at("pointerup", 150);
  assert.equal(t.v(), 30);
});

test("a right button press does not move the value", () => {
  const t = slider({ value: 30 });
  t.at("pointerdown", 150, { button: 2 }); t.at("pointerup", 150, { button: 2 });
  assert.equal(t.v(), 30);
});

test("a bare range input gets its wrapper when mounted", () => {
  const { p } = slider();
  const input = p.el("input", { type: "range", min: "0", max: "10", value: "5" }, p.document.body);
  const api = p.window.hySlider.mount(input);
  assert.equal(input.parentElement.className, "hy-slider");
  assert.equal(api.el, input.parentElement);
  assert.equal(p.window.hySlider.mount(input.parentElement), api, "a second mount gives the same object");
});

test("DialKit's update moves the slider without calling back, a person's input calls back", () => {
  const { p } = slider();
  const host = p.el("div", {}, p.document.body), got = [];
  const d = p.window.hySlider.dial(host, { label: "Exposure", min: -1, max: 1, step: 0.1, value: 0.2, onChange: v => got.push(v) });
  const input = host.querySelector("input");
  d.update({ label: "Exposure", min: -1, max: 1, step: 0.1, value: 0.5, onChange: v => got.push(v) });
  assert.equal(+input.value, 0.5);
  assert.deepEqual(got, []);
  input.value = "0.7"; input.dispatchEvent(new p.window.Event("input", { bubbles: true }));
  assert.deepEqual(got, [0.7]);
  assert.equal(host.querySelector(".hy-slider-l").textContent, "Exposure");
});
