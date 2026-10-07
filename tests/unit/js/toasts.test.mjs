// ui/toasts.js: the kind of a notification, its stack and how long each stays
import test from "node:test";
import assert from "node:assert/strict";
import { page } from "./load.mjs";

function toasts() {
  const p = page({ scripts: ["ui/toasts.js"] });
  const box = () => p.document.getElementById("hyToasts");
  const live = () => (box() ? box().children.filter(el => !el._gone).map(el => el._text) : []);
  return { p, toast: (...a) => p.window.hyToast(...a), box, live };
}

test("the words decide the kind when the caller gives none, in English and Russian", () => {
  const { toast } = toasts();
  const kind = t => toast(t).className.replace("ht ", "");
  assert.equal(kind("Couldn't save the board"), "error");
  assert.equal(kind("Не удалось открыть файл"), "error");
  assert.equal(kind("Connection was reset"), "error");
  assert.equal(kind("Saved"), "success");
  assert.equal(kind("Версия сохранена"), "success");
  assert.equal(kind("Back on the canvas: 3 frames"), "success");
  assert.equal(kind("3 frames moved"), "info");
});

test("a kind given by the caller wins over the words", () => {
  const { toast } = toasts();
  assert.equal(toast("Saved, but the error log grew", "info").className, "ht info");
});

test("an empty notification shows nothing", () => {
  const { toast, box } = toasts();
  assert.equal(toast("   "), undefined);
  assert.equal(box(), null);
});

test("the same words again make no copy, the one shown stays", () => {
  const { toast, live } = toasts();
  const a = toast("Saved"), b = toast("Saved");
  assert.equal(a, b);
  assert.deepEqual(live(), ["Saved"]);
});

test("a notification leaves after its time: info 3.2 s, an error 5.2 s", () => {
  const { p, toast, live } = toasts();
  toast("Note one", "info");
  p.tick(3100); assert.deepEqual(live(), ["Note one"]);
  p.tick(200); assert.deepEqual(live(), []);
  toast("It failed", "error");
  p.tick(5100); assert.deepEqual(live(), ["It failed"]);
  p.tick(200); assert.deepEqual(live(), []);
});

test("a card that left is taken out of the page after its fade", () => {
  const { p, toast, box } = toasts();
  toast("Note", "info");
  p.tick(3300); assert.equal(box().children.length, 1);
  p.tick(400); assert.equal(box().children.length, 0);
});

test("newer cards stay a little longer, so a stack leaves one after another, the oldest first", () => {
  const { p, toast, live } = toasts();
  toast("one", "info"); toast("two", "info"); toast("three", "info");
  p.tick(3300); assert.deepEqual(live(), ["two", "three"]);
  p.tick(400); assert.deepEqual(live(), ["three"]);
  p.tick(400); assert.deepEqual(live(), []);
});

test("five at most: a sixth makes the oldest passing one leave, a sticky one stays", () => {
  const { toast, live } = toasts();
  toast("sticky", "info", { sticky: true });
  for (const n of ["a", "b", "c", "d", "e"]) toast(n, "info");
  assert.deepEqual(live(), ["sticky", "b", "c", "d", "e"]);
});

test("a sticky notification stays until its close button is pressed", () => {
  const { p, toast, live } = toasts();
  const el = toast("Act on this", "info", { sticky: true });
  p.tick(60000); assert.deepEqual(live(), ["Act on this"]);
  const x = el.querySelector("button.x");
  assert.equal(x.title, "Close");
  assert.equal(x.getAttribute("aria-label"), "Close notification");
  p.fire(el, "click"); assert.deepEqual(live(), ["Act on this"], "a click on the card itself does not close a sticky one");
  p.fire(x, "click"); assert.deepEqual(live(), []);
});

test("a click on a passing notification closes it", () => {
  const { p, toast, live } = toasts();
  const el = toast("Note", "info");
  p.fire(el, "click");
  assert.deepEqual(live(), []);
});

test("the pointer on the stack holds every timer, leaving it starts them again oldest first", () => {
  const { p, toast, box, live } = toasts();
  toast("one", "info"); toast("two", "info");
  p.fire(box(), "mouseenter", {}, { bubbles: false });
  p.tick(20000); assert.deepEqual(live(), ["one", "two"]);
  p.fire(box(), "mouseleave", {}, { bubbles: false });
  p.tick(2000); assert.deepEqual(live(), ["two"]);
  p.tick(600); assert.deepEqual(live(), []);
});

test("inside a frame the top page's stack shows the notification", () => {
  const top = page({ scripts: ["ui/toasts.js"] });
  const inner = page({ scripts: ["ui/toasts.js"], globals: {} });
  inner.window.parent = top.window;
  inner.window.hyToast("From the canvas", "success");
  assert.equal(inner.document.getElementById("hyToasts"), null);
  assert.equal(top.document.getElementById("hyToasts").children[0]._text, "From the canvas");
});

test("the text is shown as text, never as markup", () => {
  const { toast } = toasts();
  const el = toast("<img src=x onerror=alert(1)>", "info");
  assert.equal(el.querySelector("img"), null);
  assert.equal(el.querySelector("span").textContent, "<img src=x onerror=alert(1)>");
});
