// ui/modes.js: which mode of the dock's switch is chosen and which can be entered, from the open editor and the selection
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

// the dock and two plugin modes: Image enters for one picture, 3D for one 3D card
function modes({ sel = [] } = {}) {
  const p = page({ scripts: ["ui/modes.js"] });
  const dock = p.el("div", { id: "dock" }, p.document.body);
  const state = { sel, open: null, log: [] };
  const M = p.window.hyModes({ dock, sel: () => state.sel });
  const def = (key, order, ok) => ({
    label: key, order, title: `${key}: open`, hint: `${key}: select one`,
    isOpen: () => state.open === key,
    target: ids => (ids.length === 1 && ok(ids[0]) ? ids[0] : null),
    enter: id => { state.log.push(["enter", key, id]); state.open = key; },
    leave: () => { state.log.push(["leave", key]); state.open = null; },
  });
  M.add("3d", def("3d", 30, id => id.startsWith("m")));
  M.add("image", def("image", 10, id => id.startsWith("p")));
  const btn = k => M.el.querySelector(`button[data-mode="${k}"]`);
  const sync = () => { M.sync(); p.tick(16); };
  return { p, M, dock, state, btn, sync, click: k => p.fire(btn(k), "click") };
}

test("Board comes first and the plugin modes follow by their order", () => {
  const { M } = modes();
  assert.deepEqual([...M.el.querySelectorAll(":scope > button")].map(b => b.dataset.mode), ["board", "image", "3d"]);
  // the switch is the dock's last part, after a hairline (owner 2026-10-06: «look how Figma's switch is made, it's on the right»)
  assert.equal(M.el.parentElement.id, "modesw");
  assert.equal(M.el.parentElement.parentElement.lastElementChild, M.el.parentElement, "the switch is last in the dock");
  assert.equal(M.el.previousElementSibling.className, "msep");
});

test("with nothing open Board is chosen and a mode with no target is disabled with its hint", () => {
  const { btn } = modes();
  assert.equal(btn("board").getAttribute("aria-pressed"), "true");
  assert.equal(btn("image").getAttribute("aria-disabled"), "true");
  assert.equal(btn("image").dataset.tip, "image: select one");   // the tooltip says what enables it
  assert.equal(btn("image").title, "", "no native tooltip beside ours");
  assert.equal(btn("board").getAttribute("aria-disabled"), "false");
});

test("selecting a card a mode can open enables that mode only", () => {
  const { state, btn, sync } = modes();
  state.sel = ["p1"]; sync();
  assert.equal(btn("image").getAttribute("aria-disabled"), "false");
  assert.equal(btn("image").dataset.tip, "image");   // the name alone
  assert.equal(btn("image").getAttribute("aria-description"), "image: open");
  assert.equal(btn("3d").getAttribute("aria-disabled"), "true");
});

test("two selected cards enable neither mode", () => {
  const { state, btn, sync } = modes();
  state.sel = ["p1", "p2"]; sync();
  assert.equal(btn("image").getAttribute("aria-disabled"), "true");
});

test("a click on an enabled mode opens its editor for the selected card", () => {
  const { state, click, btn, p } = modes({ sel: ["m7"] });
  click("3d"); p.tick(16);
  assert.deepEqual(state.log, [["enter", "3d", "m7"]]);
  assert.equal(btn("3d").getAttribute("aria-pressed"), "true");
  assert.equal(btn("board").getAttribute("aria-pressed"), "false");
});

test("enter(key, ids) opens a mode as its segment does, for the cards given, and says whether it went in", () => {
  // a double click on a picture enters Image this way (owner 2026-10-07), whatever was selected before
  const { M, state, btn, p } = modes({ sel: [] });
  assert.equal(M.enter("image", ["m7"]), false, "Image takes no 3D card");
  assert.equal(M.enter("nope", ["p1"]), false, "no such mode");
  assert.equal(M.enter("image", ["p1"]), true); p.tick(16);
  assert.deepEqual(state.log, [["enter", "image", "p1"]]);
  assert.equal(btn("image").getAttribute("aria-pressed"), "true");
  assert.equal(M.enter("image", ["p2"]), false, "already open");
});

test("a click on a disabled mode does nothing", () => {
  const { state, click } = modes({ sel: [] });
  click("image");
  assert.deepEqual(state.log, []);
});

test("Board leaves the open editor", () => {
  const { state, click, btn, p } = modes({ sel: ["m7"] });
  click("3d"); click("board"); p.tick(16);
  assert.deepEqual(state.log, [["enter", "3d", "m7"], ["leave", "3d"]]);
  assert.equal(btn("board").getAttribute("aria-pressed"), "true");
});

test("the open editor's mode stays enabled even when the selection no longer fits it", () => {
  const { state, click, btn, sync } = modes({ sel: ["m7"] });
  click("3d"); state.sel = []; sync();
  assert.equal(btn("3d").getAttribute("aria-disabled"), "false");
});

test("another mode while an editor is open: the open one leaves first, then the other enters", () => {
  const { state, click, p } = modes({ sel: ["m7"] });
  click("3d");
  state.sel = ["p1"]; p.tick(16);
  click("image");
  assert.deepEqual(state.log, [["enter", "3d", "m7"], ["leave", "3d"]]);
  p.tick(40);
  assert.deepEqual(state.log, [["enter", "3d", "m7"], ["leave", "3d"], ["enter", "image", "p1"]]);
});

test("an editor that asks before closing is waited for, then the other mode enters", () => {
  const p = page({ scripts: ["ui/modes.js"] });
  const dock = p.el("div", { id: "dock" }, p.document.body);
  let open = "a"; const log = [];
  const M = p.window.hyModes({ dock, sel: () => ["x"] });
  M.add("a", { label: "A", order: 10, isOpen: () => open === "a", target: () => "x", enter: id => { log.push("enter a " + id); open = "a"; }, leave: () => { log.push("leave a"); p.window.setTimeout(() => { open = null; }, 300); } });
  M.add("b", { label: "B", order: 20, isOpen: () => open === "b", target: () => "x", enter: id => { log.push("enter b " + id); open = "b"; }, leave: () => { open = null; } });
  p.tick(16);
  p.fire(M.el.querySelector('[data-mode="b"]'), "click");
  assert.deepEqual(log, ["leave a"]);
  p.tick(280); assert.deepEqual(log, ["leave a"], "not while A is still open");
  p.tick(60); assert.deepEqual(log, ["leave a", "enter b x"]);
});

test("an editor that never closes is given up on after about four seconds", () => {
  const p = page({ scripts: ["ui/modes.js"] });
  const dock = p.el("div", { id: "dock" }, p.document.body);
  const log = [];
  const M = p.window.hyModes({ dock, sel: () => ["x"] });
  M.add("a", { label: "A", order: 10, isOpen: () => true, target: () => "x", enter: () => log.push("enter a"), leave: () => log.push("leave a") });
  M.add("b", { label: "B", order: 20, isOpen: () => false, target: () => "x", enter: () => log.push("enter b"), leave() {} });
  p.fire(M.el.querySelector('[data-mode="b"]'), "click");
  p.tick(10000);
  assert.deepEqual(log, ["leave a"]);
  assert.equal(p.clock.pending() <= 2, true, "the waiting interval stopped");
});

test("a plugin whose isOpen or target throws does not break the switch", () => {
  const p = page({ scripts: ["ui/modes.js"] });
  const dock = p.el("div", {}, p.document.body);
  const M = p.window.hyModes({ dock, sel: () => ["x"] });
  M.add("bad", { label: "Bad", isOpen: () => { throw new Error("boom"); }, target: () => { throw new Error("boom"); } });
  p.tick(16);
  assert.equal(M.open, "board");
  assert.equal(M.el.querySelector('[data-mode="bad"]').getAttribute("aria-disabled"), "true");
});

test("Board cannot be replaced by a plugin", () => {
  const { M } = modes();
  M.add("board", { label: "Mine", order: -1 });
  assert.equal(M.el.querySelector('[data-mode="board"]').getAttribute("aria-label"), "Board");
});

test("the segments are icons alone, the name in aria-label and the tooltip", () => {
  const { M } = modes();
  for (const b of M.el.querySelectorAll(":scope > button")) {
    assert.equal(b.textContent.trim(), "", "no words in a segment at any width");
    assert.equal(b.getAttribute("aria-label"), b.dataset.name);
  }
});

test("a dock too narrow for all its buttons keeps only the modes that can be entered", () => {
  const { p, dock, M } = modes();
  // the dock is 300 px; its content is 260 px with every mode, 200 px without the disabled ones
  dock._box = { offsetWidth: 300, clientWidth: 300, scrollWidth: () => (M.el.classList.contains("few") ? 200 : 260) };
  p.window.dispatchEvent(new p.window.Event("resize")); p.tick(16);
  assert.equal(M.el.classList.contains("few"), false);
  dock._box.clientWidth = 230; p.window.dispatchEvent(new p.window.Event("resize")); p.tick(16);
  assert.equal(M.el.classList.contains("few"), true);
  dock._box.clientWidth = 500; p.window.dispatchEvent(new p.window.Event("resize")); p.tick(16);
  assert.equal(M.el.classList.contains("few"), false);
});
