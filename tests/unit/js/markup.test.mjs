// The markup builders: ui/icons.js (the tool icon family), ui/menu.js (menu items, colour row, the server helpers' notes) and
// ui/projicon.js (a project's icon and its picker). Only their output strings, parsed by the fake DOM.
import test from "node:test";
import assert from "node:assert/strict";
import { page, plain } from "./load.mjs";

const frag = (p, html) => { const d = p.el("div"); d.innerHTML = html; return d; };

/* ---- icons.js */
test("a tool icon is a 24 grid svg at the asked size, in the family's line", () => {
  const p = page({ scripts: ["ui/icons.js"] });
  const svg = frag(p, p.window.hyToolIcon("select", 20, "ic")).firstElementChild;
  assert.equal(svg.tagName, "SVG");
  assert.equal(svg.getAttribute("viewBox"), "0 0 24 24");
  assert.equal(svg.getAttribute("width"), "20");
  assert.equal(svg.getAttribute("class"), "ic");
  assert.equal(svg.getAttribute("stroke-width"), String(p.window.HY_IC_LINE));
});

test("an unknown tool icon gives no markup", () => {
  const p = page({ scripts: ["ui/icons.js"] });
  assert.equal(p.window.hyToolIcon("nope"), "");
});

test("every tool icon is drawn of shapes only, closed and without its own fill or stroke width", () => {
  const p = page({ scripts: ["ui/icons.js"] });
  for (const [name, d] of Object.entries(p.window.HY_TOOL_IC)) {
    const box = frag(p, d);
    assert.ok(box.children.length > 0, name);
    for (const el of box.querySelectorAll("*")) {
      assert.ok(["PATH", "CIRCLE", "RECT", "LINE", "POLYLINE", "ELLIPSE"].includes(el.tagName), `${name}: ${el.tagName}`);
      assert.equal(el.getAttribute("stroke-width"), null, name);
    }
    assert.equal(box.innerHTML.replace(/\s/g, "").length > 0, true);
  }
});

/* ---- menu.js */
const menu = (fetch) => page({ scripts: ["ui/icons.js", "ui/menu.js"], fetch });   // the menu draws its icons from the registry

test("a menu item has its icon, label and key caps in that order", () => {
  const p = menu();
  const b = frag(p, p.window.hyMenuItem('data-act="group"', "group", "Group", ["⌘", "G"], ' class="danger"')).firstElementChild;
  assert.equal(b.getAttribute("role"), "menuitem");
  assert.equal(b.dataset.act, "group");
  assert.equal(b.className, "danger");
  assert.deepEqual([...b.children].map(c => c.tagName), ["SVG", "SPAN", "SPAN"]);
  assert.equal(b.querySelector(".ml").textContent, "Group");
  assert.deepEqual([...b.querySelectorAll(".mk kbd")].map(k => k.textContent), ["⌘", "G"]);
});

test("a menu item with an unknown icon name keeps an empty icon place, markup is used as it is", () => {
  const p = menu();
  const a = frag(p, p.window.hyMenuItem("", "nope", "X")).firstElementChild;
  assert.ok(a.querySelector("span.mi0"));
  const b = frag(p, p.window.hyMenuItem("", '<img class="own">', "Y")).firstElementChild;
  assert.ok(b.querySelector("img.own"));
});

test("a menu item without keys has no key column", () => {
  const p = menu();
  assert.equal(frag(p, p.window.hyMenuItem("", "view", "Look", [])).querySelector(".mk"), null);
});

test("the colour row marks the current colour, «no colour» when there is none", () => {
  const p = menu();
  const none = frag(p, p.window.hyMenuColors(""));
  assert.deepEqual([...none.querySelectorAll("button.on")].map(b => b.dataset.color), [""]);
  const red = frag(p, p.window.hyMenuColors("red"));
  assert.deepEqual([...red.querySelectorAll("button.on")].map(b => b.dataset.color), ["red"]);
  assert.deepEqual([...red.querySelectorAll("button")].map(b => b.dataset.color), ["", ...Object.keys(p.window.HY_COLORS)]);
});

test("without i18n the words are English with a context prefix dropped", () => {
  const p = menu(async () => ({ ok: false, status: 404 }));
  const notes = [];
  return p.window.hyOpenFile("a.png", (t, k) => notes.push([t, k])).then(r => {
    assert.equal(r, null);
    assert.deepEqual(notes, [["The file is not there, or the server was not restarted", "error"]]);
  });
});

test("Show in Finder sends each path once and nothing for an empty list", async () => {
  const p = menu(async () => ({ ok: true, json: async () => ({}) }));
  assert.equal(await p.window.hyReveal([null, ""]), null);
  assert.equal(p.calls.fetch.length, 0);
  await p.window.hyReveal(["a/1.png", "a/1.png", "b/2.png", ""]);
  assert.deepEqual(JSON.parse(p.calls.fetch[0][1].body), { paths: ["a/1.png", "b/2.png"] });
});

test("Show in Finder says how many folders it left closed", async () => {
  const p = menu(async () => ({ ok: true, json: async () => ({ skipped: 3 }) }));
  const notes = [];
  await p.window.hyReveal(["a"], (t, k) => notes.push([t, k]));
  assert.deepEqual(notes, [["Opened 5 folders, 3 more not opened", "info"]]);
});

test("a file outside the library is told apart from a missing one", async () => {
  const p = menu(async () => ({ ok: false, status: 403 }));
  const notes = [];
  await p.window.hyReveal(["/etc/x"], t => notes.push(t));
  assert.deepEqual(notes, ["This file is outside the library"]);
});

test("the default app is asked once per file extension", async () => {
  const p = menu(async () => ({ ok: true, json: async () => ({ name: "Preview", path: "/Applications/Preview.app" }) }));
  const btn = frag(p, p.window.hyOpenItem('data-act="open"')).firstElementChild; p.document.body.appendChild(btn.parentElement);
  await p.window.hyOpenFill(btn, "a/one.PNG");
  await p.window.hyOpenFill(null, "b/two.png");
  await p.window.hyOpenFill(null, "c/three.jpg");
  assert.deepEqual(p.calls.fetch.map(c => c[0]), ["/api/defaultapp?p=a%2Fone.PNG", "/api/defaultapp?p=c%2Fthree.jpg"]);
  assert.equal(btn.querySelector(".ml").textContent, "Open in Preview");
});

/* ---- projicon.js */
const proj = () => page({ scripts: ["ui/projicon.js"] }).window.HY_PROJ;

test("a project without an icon wears the default stack of boards", () => {
  const P = proj();
  assert.ok(P.html({}).includes(P.icons.layers));
  assert.ok(P.html(null).includes(P.icons.layers));
});

test("a project's emoji is written escaped and keeps its own colours", () => {
  const P = proj();
  assert.equal(P.html({ icon: "🔥", color: "#e5484d" }, 20), '<span class="pji emo" style="--pj:20px" aria-hidden="true">🔥</span>');
  assert.ok(P.html({ icon: '<img src=x onerror="1">' }).includes("&lt;img src=x onerror=&quot;1&quot;&gt;"));
});

test("a project's icon takes its colour, escaped", () => {
  const P = proj();
  const h = P.html({ icon: "star", color: '#fff" onclick="x' });
  assert.ok(h.includes("color:#fff&quot; onclick=&quot;x"));
  assert.ok(h.includes(P.icons.star));
});

test("an object's own property names are not taken for icon names", () => {
  const P = proj();
  assert.equal(P.isIcon("constructor"), false);
  assert.equal(P.isIcon("toString"), false);
  assert.equal(P.isIcon("rocket"), true);
});

test("the picker opens on the tab of what the project wears and marks it", () => {
  const p = page({ scripts: ["ui/projicon.js"] }), P = p.window.HY_PROJ;
  const a = frag(p, P.picker({ icon: "cube", color: "#46a758" }));
  assert.equal(a.querySelector('[data-pjtab="icon"]').getAttribute("aria-selected"), "true");
  assert.deepEqual([...a.querySelectorAll('[aria-pressed="true"]')].map(b => b.dataset.pjicon || b.dataset.pjcolor), ["#46a758", "cube"]);
  const b = frag(p, P.picker({ icon: "🔥" }));
  assert.equal(b.querySelector('[data-pjtab="emoji"]').getAttribute("aria-selected"), "true");
  assert.deepEqual([...b.querySelectorAll('[aria-pressed="true"]')].map(x => x.dataset.pjemoji), ["🔥"]);
  assert.equal(b.querySelector("input[data-pjown]").getAttribute("value"), "🔥");
});

test("an emoji not in the grid still shows in the custom field", () => {
  const p = page({ scripts: ["ui/projicon.js"] }), P = p.window.HY_PROJ;
  const b = frag(p, P.picker({ icon: "🦄" }));
  assert.equal(b.querySelectorAll('[aria-pressed="true"]').length, 0);
  assert.equal(b.querySelector("input[data-pjown]").getAttribute("value"), "🦄");
});

test("the icon tab with no colour chosen marks the text colour", () => {
  const p = page({ scripts: ["ui/projicon.js"] }), P = p.window.HY_PROJ;
  const a = frag(p, P.picker({}, "icon"));
  assert.equal(a.querySelector('[data-pjcolor=""]').getAttribute("aria-pressed"), "true");
  assert.equal(a.querySelector('[data-pjicon="layers"]').getAttribute("aria-pressed"), "true");
  assert.equal(plain(P.colors).length, a.querySelectorAll("[data-pjcolor]").length - 1);
});
