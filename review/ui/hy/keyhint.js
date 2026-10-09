// @ts-check
// <hy-keyhint>: the keys of what the person is doing now, a quiet line of key caps and words beside it (owner 2026-10-08, writing a
// note: «должна быть подсказка внизу справа, или просто внизу, такая полупрозрачная: Shift+Enter — готово, чтобы было понятно. И такого
// рода подсказки я бы еще сделал много где»). One primitive for every such place: a note's text, a heading, a rename, the crop, a drag,
// the studios' tools. The look is ui/hy/keyhint.css; the caps are <hy-kbd size="s">.
//
//   const h = hyKeyHint.show(anchor, "note", [
//     { id: "done", keys: ["enter"], also: ["escape", "mod+enter"], t: "" },   // keys shown (any of them), also: counted, not shown; t "": the cap alone
//     { id: "bold", keys: ["mod+b"], t: "Bold" },
//     { id: "list", keys: ["-"], t: "List", auto: false },          // auto false: the page says when it was used, h.used("list")
//   ], { place: "inside", bare: true });
//   h.used("bold"); h.hide();
//
// Where (owner 2026-10-09 on round 12 «Key hints on the surface»): on a surface the hint is written on it, bare, in its ink, glyphs with
// no plate and no glass («просто Enter символа достаточно, даже без подложки»): inside (bottom right of the anchor, a note's corner) or
// end (a field's right end, or right after a field that is as wide as its words; with after: false it steps back when the words reach it).
// The glass capsule only where the action has no surface: below (a drag, a resize), above (over a dock, align "start" its left end),
// bottom (the window's), and top: the Hint bar, top centre under the top row, the keys of a Studio or a tool just opened. The bar goes as
// soon as one of its keys is used, stands right of Image Studio's #obar when that holds the line, and keeps out of a toast's way.
//
import { HyElement, define } from "./base.js";

export const DELAY = 300, QUIET = 3, LEARNED = 5;
const USED = "cv.keyhintUsed", MODE = "cv.keyhint";
const GLYPH = /** @type {Record<string, string>} */ ({ mod: "⌘", cmd: "⌘", meta: "⌘", shift: "⇧", alt: "⌥", option: "⌥", ctrl: "⌃", enter: "↵",
  escape: "Esc", esc: "Esc", backspace: "⌫", delete: "⌫", tab: "⇥", up: "↑", down: "↓", left: "←", right: "→" });
const KEY = /** @type {Record<string, string>} */ ({ enter: "Enter", escape: "Escape", esc: "Escape", space: " ", backspace: "Backspace",
  delete: "Backspace", tab: "Tab", up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight", shift: "Shift", alt: "Alt", option: "Alt",
  mod: "Meta", cmd: "Meta", meta: "Meta", ctrl: "Control" });
const MODS = ["mod", "cmd", "meta", "shift", "alt", "option", "ctrl"];

/** @typedef {{ id: string, keys: string[], t: string, also?: string[], auto?: boolean, stay?: boolean }} KeyHintItem */   // stay: never learned away; t "": caps only
/** @typedef {{ place?: "inside" | "end" | "below" | "above" | "bottom" | "top", align?: "start", delay?: number, field?: Element | null, bare?: boolean,
 *   after?: boolean }} KeyHintOpts */

/** A word in the app's language: this page's T, or the board's when the page is a frame inside it (Image Studio). @param {string} k */
function t(k) {
  /** @type {any} */ let T = window.T;
  if (typeof T !== "function") try { T = parent !== window ? /** @type {any} */ (parent).T : null; } catch { T = null; }
  return typeof T === "function" ? T(k) : k.replace(/^[^:]*::/, "");
}

/** @returns {"always" | "learn" | "off"} */
export function mode() {
  let v = null; try { v = localStorage.getItem(MODE); } catch {}
  return v === "always" || v === "off" ? v : "learn";
}
/** @returns {Record<string, number>} */
export function counts() { try { const o = JSON.parse(localStorage.getItem(USED) || "{}"); return o && typeof o === "object" ? o : {}; } catch { return {}; } }
/** @param {string} key */
export function usedCount(key) { return +(counts()[key] || 0); }
/** @param {string} key */
function bump(key) {
  try { const o = counts(); if ((o[key] || 0) >= LEARNED) return; o[key] = (o[key] || 0) + 1; localStorage.setItem(USED, JSON.stringify(o)); } catch {}
}
/** One count set as it is (the tips keep their place's state beside the counts, ui/hy/tip.js). @param {string} key @param {number} n */
export function setCount(key, n) {
  try { const o = counts(); if (n) o[key] = n; else delete o[key]; localStorage.setItem(USED, JSON.stringify(o)); } catch {}
}

/** The canvas that measures a field's words (where its last line ends). @type {CanvasRenderingContext2D | null} */
let ruler = null;
/**
 * Where the words of a field end, in its own px from its left edge, and its inner right edge: [end, right, line height].
 * A textarea's last line is what is left of its last paragraph after the full lines it wraps into (near enough for a hint).
 * @param {HTMLInputElement | HTMLTextAreaElement} f
 */
function wordsEnd(f) {
  const cs = getComputedStyle(f), pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0, right = f.clientWidth - pr;
  ruler = ruler || document.createElement("canvas").getContext("2d");
  let w = 0;
  if (ruler) {
    const last = (f.value || f.placeholder || "").split("\n").pop() || "";
    ruler.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    w = ruler.measureText(last).width + (parseFloat(cs.letterSpacing) || 0) * last.length;   // a heading's tight letters
    if (f.tagName === "TEXTAREA" && right - pl > 0 && w > right - pl + 1) w %= right - pl;   // it wraps: what is left on its last line
  }
  return [pl + w, right, parseFloat(cs.lineHeight) || (parseFloat(cs.fontSize) || 12) * 1.2];
}

/** The caps of one combination: "shift+enter" -> "⇧↵", "mod+b" -> "⌘B". @param {string} combo */
export function caps(combo) {
  return combo.split("+").map(p => p.toLowerCase() === "space" ? t("hint::Space") : GLYPH[p.toLowerCase()] ?? (p.length === 1 ? p.toUpperCase() : p)).join("");
}

/** Does this key event press the combination? Modifiers must match exactly (shift+enter is not enter). @param {string} combo @param {KeyboardEvent} e */
export function matches(combo, e) {
  const parts = combo.toLowerCase().split("+"), main = parts[parts.length - 1], want = new Set(parts.slice(0, -1).map(p => p === "cmd" || p === "meta" ? "mod" : p === "option" ? "alt" : p));
  if (parts.length === 1 && MODS.includes(main)) return e.key === KEY[main] || (main === "mod" && e.key === "Control");   // a held modifier
  const sign = main.length === 1 && !/[a-z0-9]/.test(main);   // a sign («-», «[», «@») may need ⇧ on some layouts: ⇧ is not compared
  if ((e.metaKey || e.ctrlKey) !== want.has("mod") || e.altKey !== want.has("alt") || (!sign && e.shiftKey !== want.has("shift"))) return false;
  if (KEY[main]) return e.key === KEY[main];
  if (/^[a-z]$/.test(main)) return e.code === "Key" + main.toUpperCase() || e.key.toLowerCase() === main;   // any layout: ⌘B is ⌘И
  if (/^[0-9]$/.test(main)) return e.code === "Digit" + main || e.key === main;
  return e.key === main || (main === "[" && e.code === "BracketLeft") || (main === "]" && e.code === "BracketRight");
}

export class HyKeyHint extends HyElement {
  connectedCallback() { this.setAttribute("aria-hidden", "true"); }
  /** @param {KeyHintItem[]} items @param {Record<string, number>} used @param {string} ctx */
  fill(items, used, ctx) {
    this.textContent = "";
    const learn = mode() === "learn";
    for (const it of items) {
      const n = learn && !it.stay ? used[ctx + "." + it.id] || 0 : 0;
      const row = document.createElement("span"); row.className = "kh-i"; row.dataset.id = it.id; if (n >= QUIET) row.setAttribute("quiet", "");
      it.keys.forEach((k, i) => {
        if (i) { const s = document.createElement("span"); s.className = "kh-or"; s.textContent = "/"; row.append(s); }
        const c = document.createElement("hy-kbd"); c.setAttribute("size", "s"); c.textContent = caps(k); row.append(c);
      });
      if (it.t) { const w = document.createElement("span"); w.className = "kh-t"; w.textContent = t(it.t.includes("::") ? it.t : "hint::" + it.t); row.append(w); }
      this.append(row);
    }
  }
}
define("hy-keyhint", HyKeyHint);

/** @type {{ hide(): void } | null} */
let current = null;

/**
 * Over the layer its anchor stands in. The hint's own z 50 (keyhint.css) is the overlay layer, under menus and dialogs, so the hint of a
 * slider in the settings window (z 62) or in a studio's side panel (z 60) was drawn under that window since bbbf923. The anchor's layer is
 * the z-index of its outermost positioned ancestor that has one: the order of the page, where this hint stands too.
 * @param {HTMLElement} el @param {Element} anchor
 */
function lift(el, anchor) {
  let z = NaN;
  for (let e = /** @type {Element | null} */ (anchor); e && e !== document.body; e = e.parentElement) {
    const s = getComputedStyle(e), v = parseInt(s.zIndex, 10);
    if (s.position !== "static" && Number.isFinite(v)) z = v;
  }
  if (z >= (parseInt(getComputedStyle(el).zIndex, 10) || 0)) el.style.zIndex = String(z + 1);
}

/**
 * Shows the keys of a context next to its anchor; returns the handle that ends it. Nothing is shown (the handle still works) when the
 * setting is off, when every item is learned, or when the anchor is gone.
 * @param {Element} anchor
 * @param {string} ctx
 * @param {KeyHintItem[]} items
 * @param {KeyHintOpts} [opts]
 */
export function show(anchor, ctx, items, opts = {}) {
  if (current) current.hide();
  const m = mode(), used = counts(), seen = new Set();
  const live = m === "off" ? [] : m === "always" ? items : items.filter(it => it.stay || (used[ctx + "." + it.id] || 0) < LEARNED);
  const el = /** @type {HyKeyHint} */ (document.createElement("hy-keyhint"));
  let on = true, raf = 0, timer = 0;
  const field = opts.field === undefined ? (anchor.contains(document.activeElement) ? document.activeElement : null) : opts.field;
  const top = opts.place === "top";
  // a use counts once per showing; the Hint bar has done its job with the first one: it goes (DESIGN.md «Семья подсказок»)
  const used1 = (/** @type {string} */ id) => {
    if (seen.has(id) || !items.some(i => i.id === id)) return; seen.add(id); if (m === "learn") bump(ctx + "." + id);
    if (top) handle.hide();
  };
  /** @param {KeyboardEvent} e */
  const onKey = e => { if (e.repeat) return; for (const it of items) if (it.auto !== false && [...it.keys, ...(it.also || [])].some(k => matches(k, e))) used1(it.id); };
  addEventListener("keydown", onKey, true);
  const fld = field && /^(INPUT|TEXTAREA)$/.test(field.tagName) ? /** @type {HTMLInputElement | HTMLTextAreaElement} */ (field) : null;
  /** @param {string} why @param {boolean} on1 */
  const quiet = (why, on1) => { if (on1) el.setAttribute(why, ""); else el.removeAttribute(why); };
  const place = () => {
    raf = 0; if (!on) return;
    if (!anchor.isConnected) { handle.hide(); return; }
    let box = /** @type {Element | null} */ (anchor); while (box && box.parentElement && !box.getBoundingClientRect().width) box = box.parentElement;   // display: contents (a dock's bar)
    const r = (box || anchor).getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight, vw = innerWidth, vh = innerHeight, gap = 8, in2 = 32;
    let x, y, out = false;
    if (top) {   // the Hint bar: top centre on the line under the top row (keyhint.css top), in the board's free part at that height
      const line = el.getBoundingClientRect().top, B = /** @type {any} */ (window).hyBars, st = document.getElementById("stage");
      let from = 0, to = vw;
      if (B && st) {   // the board (ui/bars.js): clear of the library and of a Studio's side panels where they reach the line
        const f = B.free(st, parseFloat(document.documentElement.style.getPropertyValue("--inset")) || 0, { t: line, b: line + h });
        from = f.l; to = f.r;
      } else {   // a page of its own (Image Studio): clear of its options (#obar) and of its side panels where they hold the line
        document.querySelectorAll("#obar, aside, [data-hyui], [data-hyside]").forEach(e => {
          const o = e.getBoundingClientRect(); if (!o.width || o.top >= line + h || o.bottom <= line) return;
          if (e.id !== "obar" && o.height < vh * 0.35) return;   // a side panel is tall; a short thing elsewhere on the line is not in the way
          if ((o.left + o.right) / 2 < vw / 2) from = Math.max(from, o.right + gap); else to = Math.min(to, o.left - gap);
        });
      }
      x = from + (to - from - w) / 2; y = 0;
      quiet("hush", toasted());   // a toast stands on the same line: the bar steps back while it is there
    }
    else if (opts.place === "end" && fld) {   // a field: at its right end, or right after it when its words fill it (it grows with them)
      const f = fld.getBoundingClientRect(), k = fld.offsetWidth ? f.width / fld.offsetWidth : 1, [end, right, lh] = wordsEnd(fld);
      const pb = fld.tagName === "TEXTAREA" ? parseFloat(getComputedStyle(fld).paddingBottom) || 0 : 0;
      const mid = fld.tagName === "TEXTAREA" ? fld.clientHeight - pb - Math.min(lh, fld.clientHeight) / 2 : fld.clientHeight / 2;   // its last line's middle
      y = f.top + (fld.clientTop + mid) * k - h / 2;
      if (!f.width) { x = f.left; out = true; }   // not drawn (yet): nothing to stand on
      else if (/right|end/.test(getComputedStyle(fld).textAlign)) x = f.left - w - gap / 2;   // a number typed flush right: just before it
      else if ((end + gap) * k + w <= right * k) x = f.left + right * k - w;
      else if (opts.after !== false) x = f.right + gap * 1.5;   // clear of a selection frame round it
      else { x = f.left + right * k - w; out = true; }   // the words come first: the hint steps back, they never move
    }
    else if (opts.place === "bottom") { x = (vw - w) / 2; y = vh - h - 96; }
    else if (opts.place === "above") { x = opts.align === "start" ? r.left + gap : r.left + (r.width - w) / 2; y = r.top - h - gap; }
    else if (opts.bare && r.width >= w + in2 && r.height >= h * 3) { x = r.right - w - 10; y = r.bottom - h - 8; }   // written on the thing itself, in its corner
    else if (opts.place !== "below" && r.width >= w + in2 && r.height >= h * 4) { x = r.right - w - in2 / 2; y = r.bottom - h - in2 / 2; }   // clear of the corner handles
    else { x = r.right - w; y = r.bottom + gap * 1.5; if (y + h > vh - gap) y = r.top - h - gap * 1.5; }   // clear of a selection frame
    quiet("yield", out);
    x = Math.max(gap, Math.min(x, vw - w - gap)); if (!top) y = Math.max(gap, Math.min(y, vh - h - gap));
    el.style.translate = `${Math.round(x)}px ${Math.round(y)}px`;
    raf = requestAnimationFrame(place);
  };
  const handle = {
    el, ctx,
    /** the person used an item the page recognises itself (auto: false) @param {string} id */
    used: (/** @type {string} */ id) => used1(id),
    /** a key the page stopped before the hint's own listener saw it (a mode that takes every key, ui/annotate.js) */
    key: onKey,
    hide() {
      if (!on) return; on = false; clearTimeout(timer); cancelAnimationFrame(raf); removeEventListener("keydown", onKey, true);
      if (field && field.getAttribute("aria-describedby") === el.id) field.removeAttribute("aria-describedby");
      if (current === handle) current = null;
      el.removeAttribute("shown"); setTimeout(() => el.remove(), 260);
    },
  };
  current = handle;
  if (!live.length || !anchor.isConnected) return handle;
  el.fill(live, used, ctx); el.id = "hykh-" + ctx;
  if (field && !field.hasAttribute("aria-describedby")) field.setAttribute("aria-describedby", el.id);
  if (opts.bare) { el.setAttribute("bare", ""); el.style.color = getComputedStyle(fld || anchor).color; }   // no plate: the thing's own ink on its own paper
  if (top) el.setAttribute("place", "top");
  el.dataset.ctx = ctx; (document.body || document.documentElement).append(el); lift(el, anchor); place();
  timer = setTimeout(() => { if (on) el.setAttribute("shown", ""); }, opts.delay ?? DELAY);
  return handle;
}

/** Is a toast up (ui/toasts.js, on the line under the top row), this page's or, in a studio's frame, the board's? */
function toasted() {
  /** @param {Document} d */
  const up = d => { const t = d.getElementById("hyToasts"); return !!t && [...t.children].some(c => /** @type {HTMLElement} */ (c).offsetHeight > 0); };
  try { return up(document) || (parent !== window && up(parent.document)); } catch { return up(document); }
}

/** The hint now shown, ended (a context that ends somewhere the page does not track) */
export function hide() { if (current) current.hide(); }

// the classic scripts of the pages (canvas.html, the studios) reach it as window.hyKeyHint
/** @type {any} */ (window).hyKeyHint = { show, hide, caps, matches, mode, usedCount, DELAY, QUIET, LEARNED };   // the tips: ui/hy/tip.js, window.hyTip
