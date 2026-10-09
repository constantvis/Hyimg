// The library's helpers: ui/layout-sync.js (folders like the board: the path bar's plate, the news of auto runs, the dialog's numbers),
// ui/libanchor.js (the card in view stays in place when the list's width changes) and ui/dragband.js (where the window can be dragged)
import test from "node:test";
import assert from "node:assert/strict";
import { page, plain } from "./load.mjs";

/* ---- layout-sync.js */
function layout(routes) {
  const state = { auto: false, last: null };
  const fetch = async (url, o) => {
    const r = (routes && routes(url, o, state)) || (url === "/api/layout/state" ? state : {});
    return { ok: r.__status ? r.__status < 400 : true, status: r.__status || 200, json: async () => r };
  };
  const p = page({ scripts: ["ui/layout-sync.js"], fetch });
  const toasts = [], redraws = [];
  p.window.hyToast = (t, k) => toasts.push([t, k]);
  p.window.renderFolders = () => redraws.push(1);
  return { p, state, toasts, redraws, W: p.window };
}

test("the path bar has the ⋯ button, and the «Like the board» plate only while the mode is on", async () => {
  const { W, p } = layout(); await p.flush();
  const box = p.el("div"); box.innerHTML = W.hyFsBar();
  assert.equal(box.querySelectorAll("[data-fsmenu]").length, 1);
  assert.equal(box.querySelector(".fsPill"), null);
  const on = layout((u, o, s) => (u === "/api/layout/state" ? { auto: true } : null)); await on.p.flush();
  box.innerHTML = on.W.hyFsBar();
  assert.equal(box.querySelector(".fsPill").textContent, "Like the board");
});

test("the first change stamp only notes the state, a later auto run says how many files it moved", async () => {
  const { W, state, toasts, p } = layout(); await p.flush();
  state.last = { id: 1, who: "auto", status: "done", moved: 3 };
  await W.hyFsSeen("s1");
  assert.deepEqual(toasts, []);
  state.last = { id: 2, who: "auto", status: "done", moved: 1 };
  await W.hyFsSeen("s2");
  assert.deepEqual(toasts, [["Folders arranged like the board: 1 files", "info"]]);
  await W.hyFsSeen("s2");
  assert.equal(toasts.length, 1, "the same stamp again is no news");
});

test("an auto run that failed is told as an error, once", async () => {
  const { W, state, toasts, p } = layout(); await p.flush();
  await W.hyFsSeen("a");
  state.last = { id: 5, who: "auto", status: "failed", error: "disk full" };
  await W.hyFsSeen("b"); await W.hyFsSeen("c");
  assert.deepEqual(toasts, [["Couldn't arrange the folders: disk full", "error"]]);
});

test("a run the person made in this window is not announced again as news", async () => {
  const { W, state, toasts, p } = layout(); await p.flush();
  await W.hyFsSeen("a");
  state.last = { id: 9, who: "user", status: "done", moved: 40 };
  await W.hyFsSeen("b");
  assert.deepEqual(toasts, []);
});

test("the folders are drawn again when the mode changed elsewhere", async () => {
  const { W, state, redraws, p } = layout(); await p.flush();
  await W.hyFsSeen("a"); const n = redraws.length;
  await W.hyFsSeen("b"); assert.equal(redraws.length, n, "nothing changed");
  state.auto = true; await W.hyFsSeen("c");
  assert.equal(redraws.length, n + 1);
});

test("the dialog shows the plan's numbers and its examples shortened in the middle", async () => {
  const long = "projects/shell/" + "very-long-folder-name/".repeat(5) + "photo-0001.png";
  const plan = { move: 1234, make: 3, remove: 0, stay: 10, off_board: 2, sidecars: 1234, examples: [{ from: long, to: "Page/Group/photo-0001.png" }], pages: ["Main"] };
  const { W, p } = layout(u => (u === "/api/layout/plan" ? plan : null)); await p.flush();
  await W.hyFsOpen(); await p.flush();
  const dlg = p.document.getElementById("fsDlg");
  assert.ok(dlg.classList.contains("open"));
  assert.deepEqual(dlg.querySelectorAll(".nums b").map(b => b.textContent), ["1,234", "3", "0", "12"]);
  assert.equal(dlg.querySelectorAll(".nums .hot").length, 1, "only «will move» is hot when no folder is deleted");
  assert.match(dlg.querySelector(".note").textContent, /\(1234 files\)/);
});

test("a long path in the examples keeps its start and its end around one ellipsis, 70 characters in all", async () => {
  const long = "projects/shell/" + "very-long-folder-name/".repeat(5) + "photo-0001.png";
  const plan = { move: 1, make: 0, remove: 0, stay: 0, examples: [{ from: long, to: "a.png" }] };
  const { W, p } = layout(u => (u === "/api/layout/plan" ? plan : null)); await p.flush();
  await W.hyFsOpen(); await p.flush();
  const shown = p.document.querySelector("#fsDlg .ex .was span:last-child").textContent;
  assert.equal(shown.length, 70);
  assert.equal(shown.split("…").length, 2);
  assert.ok(long.startsWith(shown.split("…")[0]) && long.endsWith(shown.split("…")[1]));
  assert.equal(p.document.querySelector("#fsDlg .ex li").title, `${long} → a.png`);
});

test("a plan that cannot be made says why and offers only Close", async () => {
  const { W, p } = layout(u => (u === "/api/layout/plan" ? { __status: 500, error: "no board" } : null)); await p.flush();
  await W.hyFsOpen(); await p.flush();
  const body = p.document.querySelector("#fsDlg .body");
  assert.equal(body.querySelector(".warn").textContent, "Couldn't work out the layout: no board");
  assert.equal(body.querySelector("[data-go]"), null);
});

/* ---- libanchor.js */
// a list of cards whose places depend on the scroll offset: card i at y = top[i] - scrollTop
function anchor() {
  const p = page({ globals: { view: [{ path: "a.png" }, { path: "b.png" }, { path: "c.png" }] } });
  const list = p.el("div", { id: "list" }, p.document.body), grid = p.el("div", { class: "grid" }, list);
  const html = p.document.documentElement; html.scrollTop = 0;
  const tops = [100, 400, 700];
  const cards = tops.map((t, i) => { const c = p.el("button", { class: "card", "data-i": String(i) }, grid); c._rect = () => ({ left: 0, top: tops[i] - html.scrollTop, width: 200, height: 280 }); return c; });
  p.document.elementFromPoint = (x, y) => cards.find(c => { const r = c.getBoundingClientRect(); return y >= r.top && y < r.bottom; }) || null;
  list._box = { clientWidth: 900 };
  p.load("ui/libanchor.js");
  return { p, list, html, tops, A: p.window.hyLibAnchor };
}

test("the card under the top band is the anchor, with its distance from the view's top", () => {
  const { A, html } = anchor();
  html.scrollTop = 350; A.note();   // the band ends at 80 px: card b (top 50 px) is under it
  assert.deepEqual({ ...A.anchor }, { path: "b.png", off: 50 });
});

test("after a reflow the anchored card is scrolled back to the same distance", () => {
  const { A, html, tops } = anchor();
  html.scrollTop = 350; A.note();
  tops[1] = 900;   // the rows above it got taller
  A.hold();
  assert.equal(html.scrollTop, 850);
  assert.equal(900 - html.scrollTop, 50);
});

test("a gap under the band keeps the last anchor", () => {
  const { A, html, p } = anchor();
  html.scrollTop = 350; A.note();
  p.document.elementFromPoint = () => null;
  html.scrollTop = 5000; A.note();
  assert.equal(A.anchor.path, "b.png");
});

/* ---- dragband.js */
function band(plates, drag) {
  const sent = [];
  const p = page({ globals: { webkit: { messageHandlers: { hyimg: { postMessage: m => sent.push(m) } } }, HY_DRAG: drag } });
  for (const [x, y, w, h, extra = {}] of plates) {
    const el = p.el(extra.tag || "div", {}, extra.parent || p.document.body);
    el._rect = { left: x, top: y, width: w, height: h }; if (extra.computed) el._computed = extra.computed;
    if (extra.kids) for (const [kx, ky, kw, kh] of extra.kids) { const k = p.el("button", {}, el); k._rect = { left: kx, top: ky, width: kw, height: kh }; }
  }
  p.load("ui/dragband.js");
  p.window.hyDragScan();
  return { p, sent, last: () => sent[sent.length - 1] };
}

test("the plates along the top become holes and the band reaches just under them", () => {
  const { last } = band([[10, 8, 200, 30], [1000, 6, 120, 36]]);
  assert.deepEqual(plain(last()), { action: "dragband", h: 48, holes: [[10, 8, 200, 30], [1000, 6, 120, 36]] });
});

test("with nothing along the top the band keeps its default height", () => {
  const { last } = band([[10, 300, 200, 30]]);
  assert.deepEqual(plain(last()), { action: "dragband", h: 52, holes: [] });
});

test("a tall panel starting at the top is a hole cut at the band's height, it does not stretch the band", () => {
  const { last } = band([[10, 8, 200, 30], [900, 0, 300, 700]]);
  assert.deepEqual(plain(last()), { action: "dragband", h: 44, holes: [[10, 8, 200, 30], [900, 0, 300, 44]] });
});

test("hidden and see-through plates are no holes, a plate that lets clicks through gives its children's", () => {
  const { last } = band([
    [10, 8, 200, 30, { computed: { visibility: "hidden" } }],
    [300, 8, 200, 30, { computed: { opacity: "0" } }],
    [600, 0, 400, 50, { computed: { pointerEvents: "none" }, kids: [[620, 10, 40, 24]] }],
  ]);
  assert.deepEqual(plain(last().holes), [[620, 10, 40, 24]]);
});

test("a box with no size of its own gives the plates it holds: a Studio's root and its session actions in the top row", () => {
  // Dev Studio's .dvui: no box, its <hy-studio-actions> (fixed, top right) and its panels (fixed, under the band) inside (owner
  // 2026-10-09: «ты не можешь ничего нажать ... Кнопки не работают вообще», the window dragged under Done)
  const { last } = band([[0, 0, 0, 0, { kids: [[900, 12, 300, 38], [12, 58, 260, 700]] }]]);
  assert.deepEqual(plain(last()), { action: "dragband", h: 56, holes: [[900, 12, 300, 38]] });
});

test("a page's background elements and their deep insides drag the window", () => {
  const { p, sent } = band([], { flat: "#stage", deep: "#world" });
  const stage = p.el("div", { id: "stage" }, p.document.body); stage._rect = { left: 0, top: 0, width: 1280, height: 800 };
  const plate = p.el("div", {}, stage); plate._rect = { left: 20, top: 10, width: 100, height: 30 };
  const world = p.el("div", { id: "world" }, stage); world._rect = { left: 0, top: 0, width: 1280, height: 800 };
  p.window.hyDragScan();
  assert.deepEqual(plain(sent[sent.length - 1].holes), [[20, 10, 100, 30]]);
});

test("the same band is not sent twice", () => {
  const { p, sent } = band([[10, 8, 200, 30]]);
  const n = sent.length; p.window.hyDragScan(); p.tick(5000);
  assert.equal(sent.length, n);
});
