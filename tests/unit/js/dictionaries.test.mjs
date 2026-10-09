// The Russian dictionaries ui/lang-*.js against each other and against the shared modules' code: every English plural and context
// key has its Russian, the forms are as many as the language has, the placeholders are the key's, no key is written twice, no page
// dictionary gives a word another Russian than the shared one, and every literal key the shared modules ask for is translated.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { UI } from "./load.mjs";

const FILES = ["lang-common.js", "lang-home.js", "lang-library.js", "lang-board.js", "lang-hy.js"];
const src = f => fs.readFileSync(path.join(UI, f), "utf8");
// each file on its own: what it hands to hyLang
const dict = Object.fromEntries(FILES.map(f => { let d = null; vm.runInNewContext(src(f), { hyLang: x => { d = x; } }); return [f, d]; }));
const bare = k => k.replace(/^[\w-]+::/, "");
const holes = s => [...String(s).matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(",");

test("every dictionary hands hyLang an English and a Russian table", () => {
  for (const f of FILES) {
    assert.ok(dict[f], f);
    assert.equal(typeof dict[f].en, "object", f);
    assert.equal(typeof dict[f].ru, "object", f);
  }
});

test("every English plural or context key has its Russian in the same dictionary", () => {
  for (const f of FILES) for (const k of Object.keys(dict[f].en)) assert.ok(k in dict[f].ru, `${f}: «${k}» has no Russian`);
});

test("English plurals have two forms, Russian plurals three", () => {
  for (const f of FILES) {
    for (const [k, v] of Object.entries(dict[f].en)) if (Array.isArray(v)) assert.equal(v.length, 2, `${f} en «${k}»`);
    for (const [k, v] of Object.entries(dict[f].ru)) if (Array.isArray(v)) assert.equal(v.length, 3, `${f} ru «${k}»`);
  }
});

test("a key with {n} in its English table is a plural, and its forms all say {n}", () => {
  for (const f of FILES) for (const [k, v] of Object.entries(dict[f].en)) {
    if (!/\{n\}/.test(k)) continue;
    assert.ok(Array.isArray(v), `${f} en «${k}»`);
    for (const form of v) assert.match(form, /\{n\}/, `${f} en «${k}»: «${form}»`);
  }
});

test("every translation has exactly the placeholders of its key, in every form", () => {
  const bad = [];
  for (const f of FILES) for (const t of ["en", "ru"]) for (const [k, v] of Object.entries(dict[f][t]))
    for (const form of [].concat(v)) if (holes(form) !== holes(bare(k))) bad.push(`${f} ${t} «${k}» → «${form}»`);
  assert.deepEqual(bad, []);
});

// the keys as written in the source, per table: an object literal keeps only the last of two equal keys, silently
function writtenKeys(text) {
  const out = { en: [], ru: [] }; let depth = 0, table = null, i = 0, lastWord = "";
  while (i < text.length) {
    const c = text[i];
    if (c === "/" && text[i + 1] === "/") { i = text.indexOf("\n", i); if (i < 0) break; continue; }
    if (c === '"' || c === "'") {
      let j = i + 1; while (text[j] !== c) j += text[j] === "\\" ? 2 : 1;
      const s = JSON.parse('"' + text.slice(i + 1, j).replace(/\\'/g, "'") + '"');
      let k = j + 1; while (/\s/.test(text[k])) k++;
      if (depth === 2 && table && text[k] === ":") out[table].push(s);
      i = j + 1; continue;
    }
    if (/[A-Za-z_]/.test(c)) { let j = i; while (/\w/.test(text[j])) j++; lastWord = text.slice(i, j); i = j; continue; }
    if (c === "{") { depth++; if (depth === 2) table = lastWord === "en" || lastWord === "ru" ? lastWord : null; }
    if (c === "}") { if (depth === 2) table = null; depth--; }
    i++;
  }
  return out;
}

test("no key is written twice in one table", () => {
  const dup = [];
  for (const f of FILES) {
    const w = writtenKeys(src(f));
    assert.equal(w.ru.length > 0, true, f);
    for (const t of ["en", "ru"]) { const seen = new Set(); for (const k of w[t]) { if (seen.has(k)) dup.push(`${f} ${t} «${k}»`); seen.add(k); } }
  }
  assert.deepEqual(dup, []);
});

test("the source scan sees every key of the tables", () => {
  for (const f of FILES) {
    const w = writtenKeys(src(f));
    assert.deepEqual(new Set(w.ru), new Set(Object.keys(dict[f].ru)), f);
  }
});

test("a page dictionary never gives a word another Russian than the shared one", () => {
  const common = dict["lang-common.js"].ru, clash = [];
  for (const f of FILES.slice(1)) for (const [k, v] of Object.entries(dict[f].ru))
    if (k in common && JSON.stringify(common[k]) !== JSON.stringify(v)) clash.push(`${f} «${k}»: ${JSON.stringify(v)} vs lang-common ${JSON.stringify(common[k])}`);
  assert.deepEqual(clash, []);
});

// the literal keys a shared module asks for: t("...") / T("...")
const asked = f => [...new Set([...src(f).matchAll(/\b[tT]\(\s*"((?:[^"\\]|\\.)*)"/g)].map(m => JSON.parse('"' + m[1] + '"')))];

test("every key the shared modules ask for has its Russian in lang-common.js", () => {
  // menu.js is being edited by another session right now; modes.js, notelink.js, annotate.js and comments.js live on the board only (their words
  // are in lang-board.js); homebell.js is Home's own (lang-home.js); cardfav.js, the ♥ on HTML cards, is the board's too, and so are textdoc.js
  // and connectors.js (the arrows between anything)
  const skip = new Set(["menu.js", "modes.js", "notelink.js", "annotate.js", "comments.js", "grid.js", "i18n.js", "homebell.js", "cardfav.js", "textdoc.js",
    "connectors.js"]);
  const common = dict["lang-common.js"].ru, missing = [];
  for (const f of fs.readdirSync(UI).filter(f => f.endsWith(".js") && !f.startsWith("lang-") && !skip.has(f)))
    for (const k of asked(f)) if (!(k in common)) missing.push(`${f}: «${k}»`);
  assert.deepEqual(missing, []);
});

test("Home's news and bell (homebell.js, Home only) have their words in Home's dictionary", () => {
  const home = dict["lang-home.js"].ru;
  for (const k of asked("homebell.js")) assert.ok(k in home, `homebell.js: «${k}»`);
});

test("Arrange's grids (grid.js) have their words in the board's dictionary", () => {
  const board = dict["lang-board.js"].ru;
  for (const k of asked("grid.js")) assert.ok(k in board, `grid.js: «${k}»`);
});

test("the ♥ on HTML cards (cardfav.js) has its words in the board's dictionary", () => {
  const board = dict["lang-board.js"].ru;
  for (const k of asked("cardfav.js")) assert.ok(k in board, `cardfav.js: «${k}»`);
});

test("the arrows between anything (connectors.js) have their words in the board's dictionary", () => {
  const board = { ...dict["lang-common.js"].ru, ...dict["lang-board.js"].ru };
  for (const k of asked("connectors.js")) assert.ok(k in board, `connectors.js: «${k}»`);
});

test("a text document (textdoc.js) has its words in the board's dictionary", () => {
  const board = dict["lang-board.js"].ru;
  for (const k of asked("textdoc.js")) assert.ok(k in board, `textdoc.js: «${k}»`);
});

test("the dock's mode switch has its words in the board's dictionary", () => {
  const board = dict["lang-board.js"].ru;
  for (const k of asked("modes.js")) assert.ok(k in board, `modes.js: «${k}»`);
});

test("what a note links (notelink.js) names every kind in the board's dictionary", () => {
  const board = dict["lang-board.js"].ru, en = dict["lang-board.js"].en;
  for (const k of asked("notelink.js")) assert.ok(k in board, `notelink.js: «${k}»`);
  // the kinds' words are asked through a table, not a literal T("…"): each a plural in both languages
  const kinds = [...src("notelink.js").matchAll(/"(\{n\} [^"]+)"/g)].map(m => m[1]);
  assert.ok(kinds.length >= 9);
  for (const k of kinds) assert.ok(Array.isArray(board[k]) && board[k].length === 3 && Array.isArray(en[k]), `notelink.js: «${k}»`);
});
