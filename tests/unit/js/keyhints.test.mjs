// ui/keyhints.js: the key caps on buttons show only while ⌘ is held a moment
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

function hints() {
  const p = page({ scripts: ["ui/keyhints.js"] });
  const on = () => p.document.documentElement.classList.contains("hy-keys");
  const key = (type, key, mods = {}) => p.fire(p.window, type, Object.assign({ key, metaKey: key === "Meta" && type === "keydown" }, mods));
  return { p, on, key };
}

test("holding cmd shows the key hints after a moment, not at once", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta");
  p.tick(200); assert.equal(on(), false);
  p.tick(30); assert.equal(on(), true);
});

test("releasing cmd hides the key hints", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta"); p.tick(300);
  key("keyup", "Meta");
  assert.equal(on(), false);
});

test("a cmd shortcut pressed before the moment passes never flashes the hints", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta"); p.tick(100);
  key("keydown", "c", { metaKey: true });
  p.tick(500);
  assert.equal(on(), false);
});

test("a cmd and wheel zoom hides the hints and keeps them away while cmd stays down", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta"); p.tick(300); assert.equal(on(), true);
  p.fire(p.window, "wheel", { metaKey: true });
  assert.equal(on(), false);
  key("keydown", "Meta"); p.tick(500);   // the key repeats while held
  assert.equal(on(), false);
  key("keyup", "Meta");
  key("keydown", "Meta"); p.tick(300);   // a new press after the zoom shows them again
  assert.equal(on(), true);
});

test("the window losing focus hides the hints", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta"); p.tick(300);
  p.fire(p.window, "blur", {}, { bubbles: false });
  assert.equal(on(), false);
});

test("the pointer moving without cmd hides hints left on by a lost key up", () => {
  const { p, on, key } = hints();
  key("keydown", "Meta"); p.tick(300);
  p.fire(p.window, "pointermove", { metaKey: false });
  assert.equal(on(), false);
});

test("hyKeyHints sets the state for the page and its same-origin frames", () => {
  const { p, on } = hints();
  const frameDoc = page().document, frame = p.el("iframe", {}, p.document.body);
  Object.defineProperty(frame, "contentDocument", { value: frameDoc });
  p.window.hyKeyHints(true);
  assert.equal(on(), true);
  assert.equal(frameDoc.documentElement.classList.contains("hy-keys"), true);
  p.window.hyKeyHints(false);
  assert.equal(frameDoc.documentElement.classList.contains("hy-keys"), false);
});
