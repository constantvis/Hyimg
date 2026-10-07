// ui/i18n.js: T() in English and Russian (plurals, placeholders, context keys, numbers, «ago»), T.dom on static markup
import test from "node:test";
import assert from "node:assert/strict";
import { page, plain } from "./load.mjs";

const en = () => page({ scripts: ["ui/i18n.js"] });
const ru = (extra = {}) => page({ scripts: ["ui/i18n.js"], storage: { "cv.lang": "ru" }, ...extra });

test("English is the language when nothing chose one", () => {
  const p = en();
  assert.equal(p.window.T.lang, "en");
  assert.equal(p.document.documentElement.lang, "en");
});

test("the app's language from the Mac app wins over the stored setting", () => {
  const p = page({ scripts: ["ui/i18n.js"], storage: { "cv.lang": "en" }, globals: { HY_LANG: "ru" } });
  assert.equal(p.window.T.lang, "ru");
});

test("an unknown language setting falls back to English", () => {
  const p = page({ scripts: ["ui/i18n.js"], storage: { "cv.lang": "de" } });
  assert.equal(p.window.T.lang, "en");
});

test("a Russian page stays unpainted until its static markup is translated", () => {
  const p = ru();
  assert.ok(p.document.documentElement.classList.contains("t-wait"));
  p.window.T.dom();
  assert.ok(!p.document.documentElement.classList.contains("t-wait"));
});

test("an English key without a translation shows as it is, its context dropped", () => {
  const { T } = en().window;
  assert.equal(T("Show in Finder"), "Show in Finder");
  assert.equal(T("page::Delete"), "Delete");
});

test("placeholders are filled, numbers in the language's grouping, unknown ones left as written", () => {
  const p = en(); const { T } = p.window;
  assert.equal(T("Delete «{name}»?", { name: "A" }), "Delete «A»?");
  assert.equal(T("{n} files", { n: 1234 }), "1,234 files");
  assert.equal(T("year {y}", { y: "2026" }), "year 2026", "a string stays as it is");
  assert.equal(T("{a} and {b}", { a: 1 }), "1 and {b}");
});

test("English plurals: one and other", () => {
  const p = en(); p.window.hyLang({ en: { "{n} frames": ["{n} frame", "{n} frames"] } });
  const { T } = p.window;
  assert.deepEqual([0, 1, 2, 1.5].map(n => T("{n} frames", { n })), ["0 frames", "1 frame", "2 frames", "1.5 frames"]);
});

test("Russian plurals pick one of three forms by the number's last digits", () => {
  const p = ru(); p.window.hyLang({ ru: { "{n} frames": ["{n} кадр", "{n} кадра", "{n} кадров"] } });
  const { T } = p.window;
  const form = n => T("{n} frames", { n }).replace(/^-/, "").replace(/^[\d\s ,]+/, "");
  assert.deepEqual([1, 2, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111, 112, 0].map(form),
    ["кадр", "кадра", "кадра", "кадров", "кадров", "кадров", "кадров", "кадр", "кадра", "кадров", "кадр", "кадров", "кадров", "кадров"]);
  assert.equal(form(1.5), "кадра", "a fraction takes the «two» form");
  assert.equal(form(-21), "кадр", "a negative number by its size");
});

test("a Russian number is grouped with a narrow space", () => {
  const { T } = ru().window;
  assert.match(T.num(1234567), /^1\s1?234\s567$|^1[  ]234[  ]567$/);
  assert.equal(T.num(1234567).replace(/[   ]/g, " "), "1 234 567");
});

test("a Russian key without a translation shows its English and is listed as missing, once", () => {
  const p = ru(); const { T } = p.window;
  assert.equal(T("Nothing here"), "Nothing here");
  T("Nothing here");
  assert.deepEqual(plain(p.window.__tMiss), ["Nothing here"]);
  assert.equal(T.has("Nothing here"), false);
  assert.equal(T.has("just now"), true);
});

test("a Russian plural missing its translation uses the English forms", () => {
  const p = ru(); p.window.hyLang({ en: { "{n} notes": ["{n} note", "{n} notes"] } });
  assert.equal(p.window.T("{n} notes", { n: 1 }), "1 note");
});

test("«ago» counts seconds, minutes, hours and days, then gives the date", () => {
  const { T } = en().window, now = Date.UTC(2026, 9, 6, 12, 0, 0);
  const ago = s => T.ago(now - s * 1000, now);
  assert.equal(ago(10), "just now");
  assert.equal(ago(44), "just now");
  assert.equal(ago(45), "1 min ago");
  assert.equal(ago(59 * 60), "59 min ago");
  assert.equal(ago(3600), "1 h ago");
  assert.equal(ago(86400 * 2), "2 d ago");
  assert.equal(ago(86400 * 8), T.date(now - 86400 * 8 * 1000, { day: "numeric", month: "short" }));
  assert.equal(ago(-60), "just now", "a time in the future is now");
});

test("«ago» in Russian", () => {
  const { T } = ru().window, now = Date.UTC(2026, 9, 6, 12);
  assert.equal(T.ago(now - 5 * 60000, now), "5 мин назад");
  assert.equal(T.ago(now, now), "только что");
});

test("T.dom puts the static markup into Russian: text, attributes and data-t keys, owner's data untouched", () => {
  const p = ru(); const { T } = p.window;
  p.window.hyLang({ ru: { "Close": "Закрыть", "Search": "Поиск", "Board": "Доска", "<b>Bold</b>": "<b>Жирный</b>" } });
  const root = p.html(`<div><button title="Close"> Close </button><input placeholder="Search"><span data-t="Board">x</span><p data-th="&lt;b&gt;Bold&lt;/b&gt;"></p><p data-not>Close</p><script>Close</script><i>My photo</i></div>`);
  T.dom(root);
  assert.equal(root.querySelector("button").textContent, " Закрыть ", "the spaces around stay");
  assert.equal(root.querySelector("button").title, "Закрыть");
  assert.equal(root.querySelector("input").getAttribute("placeholder"), "Поиск");
  assert.equal(root.querySelector("span").textContent, "Доска");
  assert.equal(root.querySelector("p[data-th] b").textContent, "Жирный");
  assert.equal(root.querySelector("p[data-not]").textContent, "Close");
  assert.equal(root.querySelector("script").textContent, "Close");
  assert.equal(root.querySelector("i").textContent, "My photo");
});

test("switching the language saves the setting and reloads after the settings sync had time", () => {
  const p = en(); const { T } = p.window;
  let told = null; p.window.hyLangChanged = v => { told = v; };
  T.set("ru");
  assert.equal(p.store.get("cv.lang"), "ru");
  assert.equal(told, "ru");
  p.tick(300); assert.equal(p.calls.reload, undefined);
  p.tick(100); return p.flush().then(() => assert.equal(p.calls.reload, 1));
});

test("choosing the language already shown does nothing", () => {
  const p = en();
  p.window.T.set("en"); p.tick(1000);
  assert.equal(p.store.has("cv.lang"), false);
  assert.equal(p.calls.reload, undefined);
});

test("a page reloads when another page changed the language, not when the app fixed it", async () => {
  const p = en();
  p.store.set("cv.lang", "ru");
  assert.equal(p.window.T.changed(), true);
  await p.flush(); assert.equal(p.calls.reload, 1);
  const q = page({ scripts: ["ui/i18n.js"], globals: { HY_LANG: "en" } });
  q.store.set("cv.lang", "ru");
  assert.equal(q.window.T.changed(), false);
});

test("a reload waits for the page to save what it has", async () => {
  const p = en(); const order = [];
  p.window.hyimgFlush = async () => { order.push("flush"); };
  p.window.location.reload = () => order.push("reload");
  await p.window.T.reload();
  assert.deepEqual(order, ["flush", "reload"]);
});
