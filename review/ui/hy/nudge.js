// @ts-check
// <hy-nudge>: one thing worth learning about what you just picked, a tip under it (owner 2026-10-11 on round 21, row 24, ♥ A «Совет под
// выделением», r21/hints-a.html; and on B: «почему нужно выбирать между одним и другим, когда тут можно сделать Б версию с общими командами и
// А версию с какими-то подсказками такими детальными»). The two together: the Hint bar at the top shows the selection's general keys every
// time (B, ui/boardhints.js through ui/hy/keyhint.js), and this line says the one thing not yet learned (A). Round 20 started it (owner on
// question 15: «проактивно можно показывать какие-то подсказки, когда что-то выбрал ... это вообще можно как практику для многого сделать»).
//
// As hints-a.html's sheet «Как это работает» says: under the selection at its left edge, on glass; after the selection has stood 1 s with
// nothing done; one at a time, the next on the next selection; gone with any action (a key, a press, the wheel), a new selection or after
// 6 s. Learned once its keys are pressed (or the page says used()), not shown again; it comes back when forgotten: 30 days without its
// keys (keyhint.js FORGET) or 3 times done the long way, through a menu or a button (way()). × closes this place's tips, until the «?»
// panel's Key hints switch is turned on again. Settings › Interface › Key hints (cv.keyhint) rules it with every hint: Always shows learned
// ones too, Off none. No setting of its own (owner: «чтобы настройками не перегружать ужасно интерфейс»).
//
//   const n = hyNudge.show("sel", [
//     { id: "grid", keys: ["alt+a"], t: "<b>lays them out as a grid</b>", long: "[data-tidy=grid]" },   // long: the way round, a click there
//     { id: "copy", keys: ["alt"], t: "<b>drag</b>: a copy", auto: false },     // auto false: the page says, hyNudge.used("sel", "copy")
//   ], { rect: () => ({ left, top, right, bottom }), clear: "#handles .tidy" });   // where the selection is now; what to keep clear of
//   hyNudge.learn("sel", items, () => sel.size > 0)   once: its keys and its long ways counted whether the tip shows or not
//   n.hide();  hyNudge.used(ctx, id);  hyNudge.way(ctx, id, quick);  hyNudge.learned(ctx, id)
import { HyElement, define, icon, t } from "./base.js";
import { caps as capsOf, counts, matches, mode, setCount } from "./keyhint.js";

export const DELAY = 1000, LIFE = 6000, LONG = 3;
/** @typedef {{ id: string, keys: string[], t: string, long?: string, auto?: boolean }} NudgeItem */
/** @typedef {{ left: number, top: number, right: number, bottom: number }} Box */
/** @typedef {{ rect: () => Box | null, clear?: string, delay?: number, life?: number }} NudgeOpts */
/** @typedef {{ ctx: string, el: HTMLElement | null, item: NudgeItem | null, hide(): void }} NudgeHandle */

const key = (/** @type {string} */ ctx, /** @type {string} */ id) => "nudge." + ctx + "." + id;
/** @param {string} ctx @param {string} id */
export const learned = (ctx, id) => (counts()[key(ctx, id)] || 0) >= 1;
/** @param {string} ctx */
export const closed = ctx => !!counts()["nudge." + ctx + "@off"];
/** The person did it the quick way (its keys), shown or not: learned. @param {string} ctx @param {string} id */
export function used(ctx, id) { way(ctx, id, true); }
/**
 * Done the quick way (true: learned) or the long way (false: through a menu or a button; the third time unlearns it, it shows again).
 * @param {string} ctx @param {string} id @param {boolean} quick
 */
export function way(ctx, id, quick) {
  const k = key(ctx, id), c = counts();
  if (quick) { if (!c[k]) setCount(k, 1); setCount(k + "@long", 0); }
  else if (c[k]) { const n = (c[k + "@long"] || 0) + 1; if (n >= LONG) { setCount(k, 0); setCount(k + "@long", 0); } else setCount(k + "@long", n); }
  if (current && current.ctx === ctx && current.item && current.item.id === id) current.hide();
}
/** × closed this place's tips; open() brings them back (the «?» panel's Key hints switch turned on). @param {string} ctx */
export function open(ctx) { setCount("nudge." + ctx + "@off", 0); }

export class HyNudge extends HyElement {
  connectedCallback() { this.setAttribute("role", "note"); }
}
define("hy-nudge", HyNudge);

/** @type {NudgeHandle | null} */
let current = null;
const NOOP = /** @type {NudgeHandle} */ ({ ctx: "", el: null, item: null, hide() {} });

/**
 * Shows the first item of a place not yet learned under the box rect() gives; returns the handle that ends it.
 * @param {string} ctx
 * @param {NudgeItem[]} items
 * @param {NudgeOpts} opts
 * @returns {NudgeHandle}
 */
export function show(ctx, items, opts) {
  if (current) current.hide();
  const m = mode();
  if (m === "off" || closed(ctx)) return NOOP;
  const it = m === "always" ? items[0] : items.find(i => !learned(ctx, i.id));
  if (!it) return NOOP;
  const el = /** @type {HTMLElement} */ (document.createElement("hy-nudge"));
  el.dataset.ctx = ctx; el.dataset.id = it.id;
  const caps = it.keys.map(capsOf).join("");
  const word = t(it.t.includes("::") ? it.t : "nudge::" + it.t);
  el.innerHTML = `${icon("tip", 13)}<span class="ng-k"></span><span class="ng-t">${word}</span>`
    + `<button type="button" class="ng-x" aria-label="${t("Hide tips here")}">${icon("close", 9, 2.2)}</button>`;
  const kk = /** @type {HTMLElement} */ (el.querySelector(".ng-k"));
  for (const c of caps.match(/Esc|Space|Пробел|./gu) || []) { const k = document.createElement("hy-kbd"); k.setAttribute("size", "m"); k.textContent = c; kk.append(k); }
  let on = true, raf = 0, timer = 0, life = 0;
  const place = () => {
    raf = 0; if (!on) return;
    const r = opts.rect(); if (!r) { handle.hide(); return; }
    const h = el.offsetHeight, w = el.offsetWidth, gap = 12;
    let x = r.left, y = r.bottom + gap;
    if (opts.clear) for (const o of document.querySelectorAll(opts.clear)) {   // clear of what stands there too (the bar under a selection)
      const q = o.getBoundingClientRect();
      if (q.width && q.left < x + w && q.right > x && q.top < y + h && q.bottom > y) y = q.bottom + gap / 2;
    }
    if (y + h > innerHeight - 96) y = r.top - h - gap;   // no room under it (the dock): over it
    x = Math.max(8, Math.min(x, innerWidth - w - 8)); y = Math.max(8, Math.min(y, innerHeight - h - 8));
    el.style.translate = `${Math.round(x)}px ${Math.round(y)}px`;
    raf = requestAnimationFrame(place);
  };
  /** @param {KeyboardEvent} e */
  const onKey = e => {
    if (e.repeat) return;
    const hit = it.auto !== false && it.keys.some(k => matches(k, e));
    if (hit) used(ctx, it.id);
    if (hit || !/^(Meta|Shift|Alt|Control|CapsLock)$/.test(e.key)) handle.hide();   // any action: it goes (a modifier alone may begin its keys)
  };
  /** @param {Event} e */
  const onDown = e => {
    const tg = /** @type {Element | null} */ (e.target);
    if (tg && tg.closest && tg.closest("hy-nudge")) return;
    handle.hide();
  };
  const onWheel = () => handle.hide();
  const handle = {
    ctx, el, item: it,
    hide() {
      if (!on) return; on = false; clearTimeout(timer); clearTimeout(life); cancelAnimationFrame(raf);
      removeEventListener("keydown", onKey, true); removeEventListener("pointerdown", onDown, true); removeEventListener("wheel", onWheel, true);
      if (current === handle) current = null;
      el.removeAttribute("shown"); setTimeout(() => el.remove(), 260);
    },
  };
  el.querySelector(".ng-x")?.addEventListener("click", e => { e.stopPropagation(); setCount("nudge." + ctx + "@off", 1); handle.hide(); });
  current = handle;
  // an action while it waits ends it too: the selection has to stand still
  addEventListener("keydown", onKey, true); addEventListener("pointerdown", onDown, true); addEventListener("wheel", onWheel, { capture: true, passive: true });
  timer = setTimeout(() => {
    if (!on) return;
    (document.body || document.documentElement).append(el); place();
    requestAnimationFrame(() => { if (on) el.setAttribute("shown", ""); });
    life = setTimeout(() => handle.hide(), opts.life ?? LIFE);
  }, opts.delay ?? DELAY);
  return handle;
}

/**
 * The ways of a place counted whether its tip shows or not, while when() says the place is there (something picked): its keys pressed
 * are the quick way (learned), a press on what an item's long finds is the long way. One listener each for the whole page.
 * @param {string} ctx @param {NudgeItem[]} items @param {() => boolean} when @param {(e: KeyboardEvent) => boolean} [typing]
 */
export function learn(ctx, items, when, typing) {
  addEventListener("keydown", e => {
    if (e.repeat || (typing && typing(e)) || !when()) return;
    for (const it of items) if (it.auto !== false && it.keys.some(k => matches(k, e))) used(ctx, it.id);
  }, true);
  addEventListener("pointerdown", e => {
    const tg = /** @type {Element | null} */ (e.target); if (!tg || !tg.closest || !when()) return;
    for (const it of items) if (it.long && tg.closest(it.long)) way(ctx, it.id, false);
  }, true);
}

/** The tip shown now (or waiting), ended. */
export function hide() { if (current) current.hide(); }

// the classic scripts of the pages (canvas.html's ui/boardhints.js, the studios) reach it as window.hyNudge
/** @type {any} */ (window).hyNudge = { show, hide, used, way, open, learn, learned, closed, DELAY, LIFE, LONG };
