// @ts-check
// <hy-stepper value="3" min="1" max="12" step="1" label="Columns">: round 15's tiny stepper (owner 2026-10-09 on r15-micro.html, control 6:
// «Все топ, все делай»; ui/hy/stepper.css). − the number + in one 22 px well, for a small whole count (a grid's columns, a padding) where a
// field is too much. The number is the spinbutton: ↑ ↓ step it, ⇧ ten steps, Home and End go to min and max; − and + do the same by pointer
// and stay out of the Tab order. hy-change { value } and change follow a change the person makes; setting value from code sends nothing.
import { HyElement, define, t } from "./base.js";

/**
 * A value kept inside min and max and on the step's grid from min.
 * @param {number} v
 * @param {number} min
 * @param {number} max
 * @param {number} step
 * @returns {number}
 */
export function stepClamp(v, min, max, step) {
  const s = step > 0 ? step : 1, lo = Number.isFinite(min) ? min : -Infinity, hi = Number.isFinite(max) ? max : Infinity;
  const base = Number.isFinite(lo) ? lo : 0, on = base + Math.round((v - base) / s) * s;
  return Math.min(hi, Math.max(lo, +on.toFixed(6)));
}

export class HyStepper extends HyElement {
  static observedAttributes = ["value", "min", "max", "step", "label", "disabled"];
  /** @type {HTMLElement | null} */
  #num = null;

  connectedCallback() {
    this.upgrade("value");
    if (!this.#num) {
      const b = (/** @type {string} */ dir, /** @type {string} */ words) => {
        const x = document.createElement("button");
        x.type = "button"; x.className = "hy-stp-b"; x.tabIndex = -1; x.dataset.dir = dir; x.textContent = dir === "-1" ? "−" : "+";
        x.setAttribute("aria-label", t(words));
        x.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); this.stepBy(+dir); });
        return x;
      };
      const n = document.createElement("b");
      n.className = "hy-stp-n"; n.tabIndex = 0; n.setAttribute("role", "spinbutton");
      n.addEventListener("keydown", e => this.#key(e));
      this.replaceChildren(b("-1", "Less"), n, b("1", "More"));
      this.#num = n;
    }
    this.#sync();
  }

  attributeChangedCallback() { this.#sync(); }

  /** @param {string} k @returns {number} */
  #n(k) { const v = this.getAttribute(k); return v === null || v.trim() === "" ? NaN : Number(v); }
  get min() { return this.#n("min"); }
  get max() { return this.#n("max"); }
  get step() { const s = this.#n("step"); return s > 0 ? s : 1; }
  /** @returns {number} */
  get value() { const v = this.#n("value"); return stepClamp(Number.isFinite(v) ? v : (Number.isFinite(this.min) ? this.min : 0), this.min, this.max, this.step); }
  set value(v) { this.setAttribute("value", String(v)); }

  /**
   * Moves the value by n steps as the person would: hy-change and change follow when it changes.
   * @param {number} n
   */
  stepBy(n) {
    if (this.flag("disabled")) return;
    this.#set(this.value + n * this.step);
  }

  focus() { this.#num ? this.#num.focus() : super.focus(); }

  /** @param {number} v */
  #set(v) {
    const was = this.value, now = stepClamp(v, this.min, this.max, this.step);
    if (now === was) return;
    this.setAttribute("value", String(now));
    this.emit("hy-change", { value: now }); this.emit("change", { value: now });
  }

  /** @param {KeyboardEvent} e */
  #key(e) {
    const big = e.shiftKey ? 10 : 1, k = e.key;
    if (k === "ArrowUp" || k === "ArrowRight") this.stepBy(big);
    else if (k === "ArrowDown" || k === "ArrowLeft") this.stepBy(-big);
    else if (k === "PageUp") this.stepBy(10);
    else if (k === "PageDown") this.stepBy(-10);
    else if (k === "Home" && Number.isFinite(this.min)) this.#set(this.min);
    else if (k === "End" && Number.isFinite(this.max)) this.#set(this.max);
    else return;
    e.preventDefault(); e.stopPropagation();
  }

  #sync() {
    const n = this.#num; if (!n) return;
    const v = this.value, off = this.flag("disabled");
    n.textContent = String(v);
    n.setAttribute("aria-valuenow", String(v));
    for (const [k, a] of [["min", "aria-valuemin"], ["max", "aria-valuemax"]]) {
      const x = this.#n(k); if (Number.isFinite(x)) n.setAttribute(a, String(x)); else n.removeAttribute(a);
    }
    const l = this.getAttribute("label"); if (l) n.setAttribute("aria-label", l); else n.removeAttribute("aria-label");
    n.setAttribute("aria-disabled", String(off)); n.tabIndex = off ? -1 : 0;
    const [less, more] = /** @type {HTMLButtonElement[]} */ ([...this.querySelectorAll(":scope > .hy-stp-b")]);
    if (less) less.disabled = off || (Number.isFinite(this.min) && v <= this.min);
    if (more) more.disabled = off || (Number.isFinite(this.max) && v >= this.max);
  }
}
define("hy-stepper", HyStepper);
