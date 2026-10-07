// ui/seg.js: the thumb of the app's one choice component sits under the chosen option
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

// a capsule of three 60 px options side by side
function seg(markup = `<div class="seg"><button>A</button><button aria-pressed="true">B</button><button>C</button></div>`) {
  const p = page();
  const root = p.html(markup);
  [...root.children].forEach((b, i) => { b._box = { offsetWidth: 60, offsetHeight: 28, offsetLeft: 2 + i * 60, offsetTop: 2 }; });
  p.load("ui/seg.js");
  const th = () => root.querySelector(":scope > i.st");
  return { p, root, th };
}

test("a seg gets one thumb, first in it, under the chosen option", () => {
  const { root, th } = seg();
  assert.ok(th());
  assert.equal(root.firstElementChild, th());
  assert.equal(th().getAttribute("aria-hidden"), "true");
  assert.equal(th().style.width, "60px");
  assert.equal(th().style.transform, "translate(62px, 2px)");
  assert.equal(th().style.opacity, "1");
  assert.ok(root.classList.contains("has-st"));
});

test("the thumb follows when the page marks another option as chosen", async () => {
  const { p, root, th } = seg();
  const [, a, b, c] = root.children;   // [thumb, A, B, C]
  b.setAttribute("aria-pressed", "false"); c.setAttribute("aria-pressed", "true");
  await p.flush();
  assert.equal(th().style.transform, "translate(122px, 2px)");
});

test("the class «on» marks a choice as aria-pressed does", () => {
  const { th } = seg(`<div class="seg"><button class="on">A</button><button>B</button></div>`);
  assert.equal(th().style.transform, "translate(2px, 2px)");
});

test("with nothing chosen the thumb fades out", () => {
  const { th } = seg(`<div class="seg"><button>A</button><button>B</button></div>`);
  assert.equal(th().style.opacity, "0");
});

test("a toggle button inside a choice is never taken as the chosen option", () => {
  const { th } = seg(`<div data-seg><button data-toggle aria-pressed="true">T</button><button aria-pressed="true">B</button></div>`);
  assert.equal(th().style.transform, "translate(62px, 2px)");
});

test("an up-down pair is not a choice and gets no thumb", () => {
  const { th } = seg(`<div class="seg updown"><button aria-pressed="true">▲</button><button>▼</button></div>`);
  assert.equal(th(), null);
});

test("calling hySeg again does not add a second thumb", () => {
  const { p, root } = seg();
  p.window.hySeg(); p.window.hySeg(root);
  assert.equal(root.querySelectorAll(":scope > i.st").length, 1);
});
