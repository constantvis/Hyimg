// ui/stars.js: the opening star field is a function of its seed, its start time and its grids, so Home and the canvas draw the same
// field from the same moment. Drawn on the page's own frames here (no Worker in the fake window), on a recording 2D context.
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

const T0 = 1759750000000;
function field({ seed = 7, age = 3000, at = T0 } = {}) {
  let now = at;
  const r3 = a => a.map(x => Math.round(x * 1000) / 1000);
  class Path2D { constructor() { this.ops = []; } rect(...a) { this.ops.push(["r", ...r3(a)]); } moveTo(...a) { this.ops.push(["m", ...r3(a)]); } arc(...a) { this.ops.push(["a", ...r3(a)]); } }
  const RealDate = Date;
  class FakeDate extends RealDate { constructor(...a) { super(...(a.length ? a : [now])); } static now() { return now; } }
  const p = page({ scripts: ["ui/stars.js"], globals: { Date: FakeDate, Path2D } });
  const cv = p.el("canvas", {}, p.document.body); cv._box = { clientWidth: 900, clientHeight: 600 };
  const spec = p.window.hyStarsDefaultSpec(900, 600, [255, 255, 255]);
  const f = p.window.hyStars(cv, { seed, t0: at - age, spec });
  // the last frame drawn: its fills after the last clear, as [colour, shapes]
  const frame = () => { const c = cv._ctx.calls, i = c.map(x => x[0]).lastIndexOf("clearRect"); return JSON.stringify(c.slice(i).filter(x => x[0] === "fill").map(x => x[1].ops)); };
  return { p, cv, f, spec, frame, set: t => { now = t; }, get now() { return now; } };
}

test("two fields with the same seed and start draw the same stars at the same moment", () => {
  const a = field(), b = field();
  assert.ok(a.frame().length > 100, "stars are drawn");
  assert.equal(a.frame(), b.frame());
});

test("another seed draws another field", () => {
  assert.notEqual(field({ seed: 7 }).frame(), field({ seed: 8 }).frame());
});

test("a field that takes over another's seed and start draws what that one draws", () => {
  const home = field({ seed: 1 }), canvas = field({ seed: 99 });
  canvas.f.take(home.f.params);
  canvas.set(home.now + 16); home.set(home.now + 16);
  canvas.p.tick(16); home.p.tick(16);
  assert.equal(canvas.frame(), home.frame());
});

test("taking the same seed and start again changes nothing", () => {
  const a = field();
  const before = a.f.params;
  a.f.take({ seed: before.seed, t0: before.t0 });
  assert.deepEqual({ ...a.f.params, specs: null }, { ...before, specs: null });
});

test("no star shows before its moment: a field at its very start is empty", () => {
  const a = field({ age: 0 });
  assert.equal(a.frame(), "[]");
});

test("landing runs from 0 to 1 over the time the last star needs", () => {
  const a = field();
  assert.equal(a.f.progress(), 0);
  a.f.land();
  a.set(a.now + 500); const p1 = a.f.progress();
  assert.ok(p1 > 0 && p1 < 1, String(p1));
  a.set(a.now + 60000);
  assert.equal(a.f.progress(), 1);
});

test("a grid the same to a hundredth of a pixel is the same grid", () => {
  const a = field();
  assert.equal(a.f.same({ ...a.spec, px: a.spec.px + 0.001 }), true);
  assert.equal(a.f.same({ ...a.spec, px: a.spec.px + 1 }), false);
  assert.equal(a.f.same({ ...a.spec, base: [5, 0] }), false);
});

// ui/stars.js in page mode (no Worker) shared one list of grids with the field, so setSpec pushed each grid twice: [32, 36, 37, 37]
// (fixed 2026-10-06: the field gets a copy)
test("at most four grids are kept: the first and the three latest", () => {
  const a = field();
  for (let i = 1; i <= 5; i++) a.f.setSpec({ ...a.spec, px: 32 + i });
  assert.deepEqual(Array.from(a.f.params.specs, s => s.s.px), [32, 35, 36, 37]);
});

test("a fade out stops the field and takes its canvas away after the fade", () => {
  const a = field();
  a.f.fadeOut(600);
  a.p.tick(600); assert.ok(a.cv.isConnected);
  a.p.tick(100); assert.equal(a.cv.isConnected, false);
  const n = a.cv._ctx.calls.length; a.p.tick(1000);
  assert.equal(a.cv._ctx.calls.length, n, "no frame after stop");
});
