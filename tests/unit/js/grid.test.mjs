// ui/grid.js: the grid the board keeps after Arrange (owner 2026-10-08), the same model as review/grids.py: reading order, "fit" cells
// from the top left, one item in one grid, a reflow after a member is deleted or resized, the cell under a point, two merged edits
import test from "node:test";
import assert from "node:assert/strict";
import { page, plain } from "./load.mjs";

const pic = (x, y, ar = 1.5) => ({ path: `a/${x}.png`, x, y, w: 300, ar });
function board() {
  return { items: { a: pic(0, 0), b: pic(380, 30), c: pic(700, -20, 1), d: pic(20, 300), e: pic(360, 330), n: { type: "note", text: "x", x: -400, y: 0, w: 300, fs: 20 } }, groups: {} };
}
const G = () => page({ scripts: ["ui/grid.js"] }).window.hyGrid;
const xy = (b, ...ids) => ids.map(i => [b.items[i].x, b.items[i].y]);
let n = 0; const newId = p => p + ++n;

test("make: reading order, columns from the longest row, fit cells from the top left", () => {
  const g = G(), b = board(), gid = g.make(b, ["e", "a", "c", "b", "d", "n"], null, false, newId);
  assert.deepEqual(plain(b.grids[gid]), { members: ["a", "b", "c", "d", "e"], cols: 3, rows: 2, gap: 24, cell: "fit" });   // the note is not a grid's
  assert.deepEqual(xy(b, "a", "b", "c", "d", "e"), [[0, -20], [324, -20], [648, -20], [0, 304], [324, 304]]);
  const L = g.layout(b, b.grids[gid]);
  assert.deepEqual(plain(L.shape), { cols: 3, rows: 2, colw: [300, 300, 300], rowh: [300, 200], x: 0, y: -20, w: 948, h: 524 });
});

test("one item in one grid; a grid lives with two members", () => {
  const g = G(), b = board(), g1 = g.make(b, ["a", "b", "c"], null, false, newId), g2 = g.make(b, ["c", "d"], null, false, newId);
  assert.deepEqual(plain(b.grids[g1].members), ["a", "b"]); assert.deepEqual(plain(b.grids[g2].members), ["c", "d"]);
  g.leave(b, ["a"]); assert.equal(b.grids[g1], undefined);
});

test("prune: a deleted member closes the gap from the old top left, a resized one reflows the grid", () => {
  const g = G(), b = board(), gid = g.make(b, ["a", "b", "c", "d", "e"], null, false, newId), cells = xy(b, "a", "b", "c", "d", "e");
  const B = JSON.parse(JSON.stringify(b)); delete b.items.a; g.prune(b, B);
  assert.deepEqual(plain(b.grids[gid].members), ["b", "c", "d", "e"]); assert.deepEqual(xy(b, "b", "c", "d"), cells.slice(0, 3));
  const B2 = JSON.parse(JSON.stringify(b)); b.items.b.w = 500; g.prune(b, B2);
  assert.deepEqual(xy(b, "c"), [[cells[0][0] + 500 + 24, cells[0][1]]]);
});

test("the cell under a point, or the one after the last", () => {
  const g = G(), cells = [{ x: 0, y: 0, w: 100, h: 100 }, { x: 124, y: 0, w: 100, h: 100 }];
  assert.equal(g.slot(cells, { x: 150, y: 40 }), 1);
  assert.equal(g.slot(cells, { x: 300, y: 40 }, { x: 248, y: 0, w: 100, h: 100 }), 2);
});

test("two edits of one grid merged: the merged order laid out again (as review/merge.py)", () => {
  const g = G(), base = board(), gid = g.make(base, ["a", "b", "c", "d", "e"], null, false, newId), cells = xy(base, "a");
  const out = JSON.parse(JSON.stringify(base)); out.grids[gid].members = ["c", "a", "b", "d", "e", "x"];
  out.items.x = pic(5000, 5000);
  g.merged(out, base, base);
  assert.deepEqual(xy(out, "c"), cells); assert.equal(out.grids[gid].rows, 2);
});
