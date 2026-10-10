// @ts-check
// Scrub a number (owner 2026-10-10 on round 16's r16-scrub.html, version A: «отлично, беру»; ui/hy/scrub.css). As Figma: the letter or the
// icon left of the number is a handle, drag it ← → and the number follows, ⇧ ten times faster, ⌥ ten times finer; a click without moving
// types the number (Enter keeps it, Esc puts it back, ↑ ↓ step by 1, ⇧ by 10); Esc while dragging puts the old value back. The pointer is
// ew-resize over the handle and stays so for the whole drag. A drag whose release this page never saw (let go over a live page's frame,
// outside the window, the capture lost) ends at the next move without a button or at the capture's loss: a hover never moves the number
// (owner 2026-10-10). One drag is one change for the page's history: begin before the first move,
// end after the last.
//
// Two ways in:
//   <hy-scrub label="X" icon="opacity" value="24" min="0" max="100" step="1" dec="0" unit="px">: a whole field, the handle, the number
//     and its unit in one 24 px well. hy-scrub-start when a drag begins, hy-input { value } at each step of it, hy-change and change
//     { value } once a drag or a typed value ends, hy-cancel when Esc put the old value back.
//   scrub(handle, { get, set, step, min, max, can, begin, end, cancel, click, field }): a page's own field (Image Studio's, 3D Studio's
//     W × H) gets the same drag on its own label; window.hyScrub is this for the classic scripts.
import { HyElement, define, icon } from "./base.js";

/**
 * How much one pixel of the pointer moves the value: ⇧ ten times, ⌥ a tenth.
 * @param {{ shiftKey?: boolean, altKey?: boolean }} e
 * @returns {number}
 */
export const scrubRate = e => (e.shiftKey ? 10 : e.altKey ? 0.1 : 1);

/**
 * A value kept inside min and max, without the float's dust.
 * @param {number} v
 * @param {number} [min]
 * @param {number} [max]
 * @returns {number}
 */
export function scrubClamp(v, min, max) {
  const lo = Number.isFinite(min) ? /** @type {number} */ (min) : -Infinity, hi = Number.isFinite(max) ? /** @type {number} */ (max) : Infinity;
  return Math.min(hi, Math.max(lo, +(+v).toFixed(6)));
}

/** @typedef {{ get: () => number, set: (v: number) => void, step?: number, min?: number, max?: number, can?: () => boolean,
 *   begin?: () => void, end?: (changed: boolean) => void, cancel?: () => void, click?: (e: PointerEvent) => void, field?: Element | null }} ScrubOpts */

/** @type {{ restore: () => void } | null} the drag under way, for Esc */
let ACTIVE = null;
// Esc while dragging: caught on the window before anything of the page (a Studio's Esc closes the Studio), once per document
if (!(/** @type {any} */ (window).__hyScrubEsc)) {
  /** @type {any} */ (window).__hyScrubEsc = true;
  globalThis.addEventListener?.("keydown", e => { if (e.key === "Escape" && ACTIVE) { e.preventDefault(); e.stopImmediatePropagation(); ACTIVE.restore(); } }, true);
}

/**
 * Makes handle drag a number (see the top of this file).
 * @param {HTMLElement} handle
 * @param {ScrubOpts} o
 * @returns {() => void} takes the drag off again
 */
export function scrub(handle, o) {
  if (/** @type {any} */ (handle).__hyScrub) return /** @type {any} */ (handle).__hyScrub;
  handle.classList.add("hy-scrub-h");
  const field = o.field || handle.parentElement;
  /** @type {{ id: number, x: number, v0: number, v: number, moved: boolean } | null} */
  let d = null;
  const stop = (/** @type {boolean} */ changed) => {
    if (!d) return;
    const was = d; d = null; ACTIVE = null;
    try { handle.releasePointerCapture(was.id); } catch (e) { /* already let go */ }
    if (field) field.classList.remove("hy-scrubbing");
    document.documentElement.classList.remove("hy-scrub-drag");
    return was;
  };
  /** @param {PointerEvent} e */
  const down = e => {
    if (e.button !== 0 || (o.can && !o.can())) return;
    e.preventDefault(); e.stopPropagation();
    try { handle.setPointerCapture(e.pointerId); } catch (err) { /* a synthetic event */ }
    const v0 = +o.get() || 0;
    d = { id: e.pointerId, x: e.clientX, v0, v: v0, moved: false };
  };
  /** @param {PointerEvent} e */
  const move = e => {
    if (!d || e.pointerId !== d.id) return;
    if (!(e.buttons & 1)) return up(e);   // the button is up: the release went elsewhere
    const dx = e.clientX - d.x;
    if (!d.moved) {
      if (Math.abs(dx) < 2) return;
      d.moved = true;
      if (field) field.classList.add("hy-scrubbing");
      document.documentElement.classList.add("hy-scrub-drag");
      ACTIVE = { restore: () => { const was = stop(false); if (!was) return; o.set(was.v0); if (o.cancel) o.cancel(); } };
      if (o.begin) o.begin();
    }
    d.x = e.clientX;
    d.v = scrubClamp(d.v + dx * (o.step || 1) * scrubRate(e), o.min, o.max);
    o.set(d.v);
  };
  /** @param {PointerEvent} e */
  const up = e => {
    if (!d || e.pointerId !== d.id) return;
    const was = stop(true);
    if (!was) return;
    if (was.moved) {   // the click that ends a drag is not a click (a <label> handle would focus its field)
      const eat = (/** @type {Event} */ ev) => { ev.preventDefault(); ev.stopPropagation(); };
      handle.addEventListener("click", eat, { capture: true, once: true }); setTimeout(() => handle.removeEventListener("click", eat, true), 0);
      if (o.end) o.end(was.v !== was.v0);
    }
    else if (o.click && e.type === "pointerup") o.click(e);
  };
  handle.addEventListener("pointerdown", down);
  handle.addEventListener("pointermove", move);
  handle.addEventListener("pointerup", up);
  handle.addEventListener("pointercancel", up);
  handle.addEventListener("lostpointercapture", up);
  const off = () => {
    stop(false); handle.classList.remove("hy-scrub-h");
    handle.removeEventListener("pointerdown", down); handle.removeEventListener("pointermove", move);
    handle.removeEventListener("pointerup", up); handle.removeEventListener("pointercancel", up);
    handle.removeEventListener("lostpointercapture", up);
    delete (/** @type {any} */ (handle)).__hyScrub;
  };
  /** @type {any} */ (handle).__hyScrub = off;
  return off;
}
/** @type {any} */ (window).hyScrub = scrub;

/**
 * A typed number: digits with a dot or a comma, a minus; nothing else is a number.
 * @param {string} s
 * @returns {number}
 */
export function scrubParse(s) {
  const t = String(s).trim().replace(/\s+/g, "").replace(",", ".").replace(/^−/, "-");
  return /^[-+]?(\d+\.?\d*|\.\d+)$/.test(t) ? +t : NaN;
}

export class HyScrub extends HyElement {
  static observedAttributes = ["value", "label", "icon", "unit", "min", "max", "dec", "disabled"];
  /** @type {HTMLInputElement | null} */
  #input = null;
  /** @type {HTMLElement | null} */
  #h = null;
  #typed = false;

  connectedCallback() {
    this.upgrade("value");
    if (!this.#input) {
      const h = document.createElement("i"), i = document.createElement("input"), u = document.createElement("span");
      h.className = "hy-scrub-l"; h.setAttribute("aria-hidden", "true");
      i.className = "hy-scrub-v"; i.inputMode = "decimal"; i.autocomplete = "off"; i.spellcheck = false;
      u.className = "hy-scrub-u";
      this.replaceChildren(h, i, u);
      this.#h = h; this.#input = i;
      const self = this;
      scrub(h, {
        get: () => this.value, set: v => this.#live(v), field: this,
        get step() { return self.#n("step") || 1; }, get min() { return self.#n("min"); }, get max() { return self.#n("max"); },
        can: () => !this.flag("disabled"), begin: () => this.emit("hy-scrub-start", { value: this.value }),
        end: changed => { if (changed) this.#done(); }, cancel: () => this.emit("hy-cancel", { value: this.value }),
        click: () => { i.focus(); i.select(); },
      });
      i.addEventListener("focus", () => { this.#typed = false; setTimeout(() => i.select(), 0); });
      i.addEventListener("input", () => { this.#typed = true; });
      i.addEventListener("blur", () => this.#commit());
      i.addEventListener("change", e => e.stopPropagation());   // the element says change itself, with the value it kept
      i.addEventListener("keydown", e => {
        e.stopPropagation();
        if (e.key === "Enter") { e.preventDefault(); this.#commit(); i.blur(); }
        else if (e.key === "Escape") { e.preventDefault(); this.#typed = false; this.#show(); i.blur(); }
        else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
          e.preventDefault(); this.#typed = false;
          const v = scrubClamp(this.value + (e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 10 : 1), this.#n("min"), this.#n("max"));
          if (v !== this.value) { this.setAttribute("value", String(v)); this.#done(); }
          i.select();
        }
      });
    }
    this.#sync();
  }

  attributeChangedCallback() { this.#sync(); }

  /** @param {string} k */
  #n(k) { const v = this.getAttribute(k); return v === null || v.trim() === "" ? NaN : Number(v); }
  /** @returns {number} */
  get value() { const v = this.#n("value"); return Number.isFinite(v) ? v : 0; }
  set value(v) { this.setAttribute("value", String(v)); }
  /** The number field inside (null before the element is in a document). */
  get input() { return this.#input; }
  /** The handle: the letter or the icon. */
  get handle() { return this.#h; }

  focus() { this.#input ? this.#input.focus() : super.focus(); }

  /** @param {number} v */
  #live(v) { this.setAttribute("value", String(v)); this.emit("hy-input", { value: this.value }); }
  #done() { const value = this.value; this.emit("hy-change", { value }); this.emit("change", { value }); }
  #commit() {
    if (!this.#typed || !this.#input) return;
    this.#typed = false;
    const v = scrubParse(this.#input.value);
    if (!Number.isFinite(v)) { this.#show(); return; }
    const now = scrubClamp(v, this.#n("min"), this.#n("max"));
    if (now !== this.value) { this.setAttribute("value", String(now)); this.#done(); } else this.#show();
  }
  #show() {
    const i = this.#input; if (!i || (document.activeElement === i && this.#typed)) return;
    const dec = this.#n("dec"), v = this.value;
    i.value = Number.isFinite(dec) ? v.toFixed(dec) : String(Math.round(v * 1000) / 1000);
  }

  #sync() {
    const h = this.#h, i = this.#input; if (!h || !i) return;
    const ic = this.getAttribute("icon"), l = this.getAttribute("label") || "";
    h.innerHTML = ic ? icon(ic, 12) || l : l;
    h.dataset.axis = /^[XYZ]$/.test(l) ? l.toLowerCase() : "";
    const u = /** @type {HTMLElement} */ (this.querySelector(":scope > .hy-scrub-u")); u.textContent = this.getAttribute("unit") || "";
    i.disabled = this.flag("disabled");
    const name = this.getAttribute("aria-label") || this.getAttribute("title") || l;
    if (name) i.setAttribute("aria-label", name);
    this.#show();
  }
}
define("hy-scrub", HyScrub);
