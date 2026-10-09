// @ts-check
// <hy-tip>: one short line about one thing you can do here, for someone who is only looking (DESIGN.md «Семья подсказок», the Tip of
// docs/glossary.md). Round 12's version 9, the pick of «Tips that do not nag» (owner 2026-10-09 on r12/docs-tips.html: «9 версия
// идеальна — делай»): still, one tip per visit (the next waits until the place shows again), a click shows the next, × on hover turns
// this place's tips off and leaves the bulb, dim, whose click brings them back; and a thing done the long way shows its quick way once,
// off or not. The look is ui/hy/tip.css, the bulb is «tip» of ui/icons.js.
//
//   const h = hyTip.show(host, "library", [
//     { id: "altx", t: "<b>⌥-click</b> a filter excludes it at once", auto: false },   // t: the line, its key words in <b>
//     { id: "ctab", t: "<b>⌃Tab</b> returns to the board you had before", keys: ["ctrl+tab"] },
//   ], { glass: false });        // appended to host; a visit: each show() takes the next tip; glass over pictures
//   hyTip.used("library", "altx")         // the page saw the tip's action done (auto: false): learned, not shown again
//   hyTip.way("library", "altx", false)   // done the long way: its quick way shows once at the place; true: the quick way, learned
//   h.hide()
//
// It learns from the key hints' counts (ui/hy/keyhint.js, cv.keyhintUsed, one for the Mac): «tip.<ctx>.<id>» is 1 once the person
// pressed the tip's keys or did its action, and the tip is not shown again. Beside them the place keeps its state: «tip.<ctx>@at» the
// next tip, «tip.<ctx>@off» closed with ×, «tip.<ctx>.<id>@told» its quick way told. Settings › Interface › Key hints (cv.keyhint) rules
// the tips too: Always shows learned ones, Until learned leaves them out, Off shows none.
import { HyElement, define, icon, t } from "./base.js";
import { counts, matches, mode, setCount } from "./keyhint.js";

/** @typedef {{ id: string, t: string, keys?: string[], auto?: boolean }} TipItem */
/** @typedef {{ glass?: boolean }} TipOpts */
/** @typedef {{ el: HyTip | null, ctx: string, next(): void, hide(): void, tell(id: string): void }} TipHandle */

/** @param {string} ctx @param {string} id */
const learned = (ctx, id) => (counts()["tip." + ctx + "." + id] || 0) >= 1;
/** @param {string} html */
const plain = html => html.replace(/<[^>]+>/g, "");

export class HyTip extends HyElement {
  connectedCallback() { this.setAttribute("role", "note"); }
}
define("hy-tip", HyTip);

/** The places now showing a tip, by context (way() finds its place here). @type {Map<string, TipHandle>} */
const places = new Map();
const NOOP = /** @type {TipHandle} */ ({ el: null, ctx: "", next() {}, hide() {}, tell() {} });

/**
 * Shows one tip of a place in host; returns the handle that ends it. Nothing is shown when the setting is off or every tip is learned.
 * @param {Element} host
 * @param {string} ctx
 * @param {TipItem[]} items
 * @param {TipOpts} [opts]
 * @returns {TipHandle}
 */
export function show(host, ctx, items, opts = {}) {
  const was = places.get(ctx); if (was) was.hide();
  const m = mode();
  /** the tips this place can show now: unlearned ones, or all of them with Always */
  const live = () => (m === "always" ? items : items.filter(it => !learned(ctx, it.id)));
  if (m === "off" || !live().length || !host.isConnected) return NOOP;
  const el = /** @type {HyTip} */ (document.createElement("hy-tip"));
  const words = (/** @type {TipItem} */ it) => t(it.t.startsWith("tip::") ? it.t : "tip::" + it.t);
  el.innerHTML = `${icon("tip", 11)}<span class="tip-t"></span><button type="button" class="tip-x" aria-label="${t("Hide tips here")}" title="${t("Hide tips here")}">`
    + `${icon("close", 9, 2.2)}</button>`;
  if (opts.glass) el.setAttribute("glass", "");
  el.dataset.ctx = ctx;
  const tt = /** @type {HTMLElement} */ (el.querySelector(".tip-t")), AT = "tip." + ctx + "@at", OFF = "tip." + ctx + "@off";
  let cur = /** @type {TipItem | null} */ (null), on = true, fade = 0;
  /** @param {TipItem} it @param {boolean} [soft] */
  const put = (it, soft) => {
    cur = it; clearTimeout(fade);
    const set = () => { tt.innerHTML = words(it); el.title = plain(words(it)); el.dataset.id = it.id; el.removeAttribute("out"); };
    if (!soft || matchMedia("(prefers-reduced-motion: reduce)").matches) { set(); return; }
    el.setAttribute("out", ""); fade = window.setTimeout(set, 300);   // the old line fades and lifts 4 px, the next comes in its place
  };
  const off = () => (counts()[OFF] || 0) >= 1;
  const shut = (/** @type {boolean} */ v) => {
    setCount(OFF, v ? 1 : 0); el.toggleAttribute("off", v);
    if (v) { el.title = t("Tips are off here · click the bulb to bring them back"); el.removeAttribute("out"); }
  };
  // a visit: this place shows the tip after the one it showed last time
  { const L = live(), at = (counts()[AT] || 0) % L.length; put(L[at]); setCount(AT, (at + 1) % L.length); }
  if (off()) shut(true);
  const next = () => {
    const L = live(); if (!L.length) { handle.hide(); return; }
    const i = cur ? L.findIndex(x => x.id === cur?.id) : -1, n = L[(i + 1) % L.length];
    put(n, true); setCount(AT, (L.indexOf(n) + 1) % L.length);
  };
  el.addEventListener("click", e => {
    const tg = /** @type {Element} */ (e.target);
    if (tg.closest(".tip-x")) { e.stopPropagation(); shut(true); return; }
    if (el.hasAttribute("off")) { if (tg.closest("svg")) { e.stopPropagation(); shut(false); if (cur) put(cur); } return; }
    e.stopPropagation(); next();
  });
  /** a tip's keys pressed while it is shown: learned (the next visit leaves it out) @param {KeyboardEvent} e */
  const onKey = e => { if (!e.repeat) for (const it of items) if (it.auto !== false && (it.keys || []).some(k => matches(k, e))) used(ctx, it.id); };
  addEventListener("keydown", onKey, true);
  /** @type {TipHandle} */
  const handle = {
    el, ctx, next,
    /** the quick way of a thing just done the long way, once, at this place even when it was closed @param {string} id */
    tell(id) { const it = items.find(x => x.id === id); if (!it || !on) return; if (el.hasAttribute("off")) shut(false); put(it, true); },
    hide() {
      if (!on) return; on = false; clearTimeout(fade); removeEventListener("keydown", onKey, true);
      if (places.get(ctx) === handle) places.delete(ctx);
      el.remove();
    },
  };
  places.set(ctx, handle);
  host.append(el);
  return handle;
}

/** The person did a tip's action (or pressed its keys): learned, it is not shown again. @param {string} ctx @param {string} id */
export function used(ctx, id) { if (mode() === "learn" && !learned(ctx, id)) setCount("tip." + ctx + "." + id, 1); }

/**
 * A thing done: the quick way (true) teaches the tip, the long way (false) shows its quick way once, now, at the place if it shows a tip.
 * @param {string} ctx @param {string} id @param {boolean | null} quick   null: neither, nothing happens
 */
export function way(ctx, id, quick) {
  if (quick) { used(ctx, id); return; }
  if (quick === null || mode() === "off") return;
  const TOLD = "tip." + ctx + "." + id + "@told", p = places.get(ctx);
  if ((counts()[TOLD] || 0) >= 1 || !p) return;
  setCount(TOLD, 1); p.tell(id);
}

/** The tip a place shows, ended. @param {string} ctx */
export function hide(ctx) { const p = places.get(ctx); if (p) p.hide(); }

// the classic scripts of the pages (v2.html's ui/libtips.js, the board's ui/boardhints.js) reach it as window.hyTip
/** @type {any} */ (window).hyTip = { show, used, way, hide };
