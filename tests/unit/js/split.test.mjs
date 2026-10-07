// ui/split.js: the splitter between stacked panel sections hands the drag to its host
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

function split() {
  const p = page({ scripts: ["ui/split.js"] });
  const el = p.el("div", {}, p.document.body), log = [];
  p.window.hySplit(el, {
    start: e => { log.push(["start", e.clientY]); return { h: 100 }; },
    move: (dy, ctx) => log.push(["move", dy, ctx.h]),
    end: ctx => log.push(["end", ctx.h]),
    reset: () => log.push(["reset"]),
  });
  const root = () => p.document.documentElement.classList.contains("hy-splitting");
  return { p, el, log, root };
}

test("a vertical drag on the splitter reports how far it moved from the press", () => {
  const { p, el, log, root } = split();
  p.fire(el, "pointerdown", { clientY: 200 });
  assert.equal(root(), true);
  assert.equal(el.classList.contains("drag"), true);
  p.fire(el, "pointermove", { clientY: 230 });
  p.fire(el, "pointermove", { clientY: 180 });
  p.fire(el, "pointerup", { clientY: 180 });
  assert.deepEqual(log, [["start", 200], ["move", 30, 100], ["move", -20, 100], ["end", 100]]);
  assert.equal(root(), false);
  assert.equal(el.classList.contains("drag"), false);
});

test("the drag ends once even when the pointer up and the capture loss both come", () => {
  const { p, el, log } = split();
  p.fire(el, "pointerdown", { clientY: 10 });
  p.fire(el, "pointerup", {}); p.fire(el, "lostpointercapture", {});
  assert.equal(log.filter(x => x[0] === "end").length, 1);
});

test("a pointer move without a press does nothing", () => {
  const { p, el, log } = split();
  p.fire(el, "pointermove", { clientY: 50 });
  assert.deepEqual(log, []);
});

test("a folded neighbour's splitter (.off) takes no drag", () => {
  const { p, el, log } = split();
  el.classList.add("off");
  p.fire(el, "pointerdown", { clientY: 10 }); p.fire(el, "pointermove", { clientY: 40 });
  assert.deepEqual(log, []);
});

test("only the main button starts a drag", () => {
  const { p, el, log } = split();
  p.fire(el, "pointerdown", { clientY: 10, button: 2 });
  assert.deepEqual(log, []);
});

test("a double click gives the sizes back to the content", () => {
  const { p, el, log } = split();
  p.fire(el, "dblclick");
  assert.deepEqual(log, [["reset"]]);
});

test("the splitter gets its look class and is returned for chaining", () => {
  const p = page({ scripts: ["ui/split.js"] }), el = p.el("div");
  assert.equal(p.window.hySplit(el), el);
  assert.ok(el.classList.contains("hy-split"));
});
