// @ts-check
// <hy-segmented value="b" size="s|m|l" variant="choice|tabs|tint|well|micro" full label="…"><button value="a">A</button>…</hy-segmented>: one choice
// of a few (ui/hy/segmented.css). Built on ui/seg.js: the element is a .seg and the thumb slides under the chosen option. A click, or
// ← → ↑ ↓ Home End on the focused option, chooses; only the chosen option is in the Tab order. hy-change { value } and change follow a
// choice made by the person; setting value from code moves the thumb and sends nothing. variant=tabs: role tablist / tab, aria-selected;
// variant=tint: a choice drawn without a track, the chosen option tinted; variant=well: a dark well, the chosen option on a grey
// plate; variant=micro: round 15's micro segments, 2 to 4 options of 18 px in a 22 px well (segmented.css).
import { HyElement, define, oneOf } from "./base.js";

// the thumb's engine: the page's ui/seg.js, or loaded here without its own pass over the page (ui/seg.js HY_SEG_MANUAL)
if (typeof window.hySeg !== "function") { window.HY_SEG_MANUAL = true; await import(new URL("../seg.js", import.meta.url).href); }

/** @typedef {"choice" | "tabs" | "tint" | "well" | "micro"} SegVariant */
/** @type {readonly SegVariant[]} */
export const SEG_VARIANTS = ["choice", "tabs", "tint", "well", "micro"];

/**
 * Where an arrow key goes in a row of n options from i: the next or previous one around the ends, Home and End.
 * @param {string} key
 * @param {number} i
 * @param {number} n
 * @returns {number} the index, or -1 for a key that does not move
 */
export function segStep(key, i, n) {
  if (n <= 0) return -1;
  if (key === "ArrowRight" || key === "ArrowDown") return (i + 1 + n) % n;
  if (key === "ArrowLeft" || key === "ArrowUp") return (i - 1 + n) % n;
  if (key === "Home") return 0;
  if (key === "End") return n - 1;
  return -1;
}

export class HySegmented extends HyElement {
  static observedAttributes = ["value", "variant", "label"];
  #built = false;

  connectedCallback() {
    this.upgrade("value");
    if (!this.#built) {
      this.#built = true;
      this.classList.add("seg");
      this.addEventListener("click", e => {
        const b = /** @type {Element} */ (e.target).closest("button");
        if (b && b.parentElement === this && !(/** @type {HTMLButtonElement} */ (b)).disabled) this.#choose(/** @type {HTMLButtonElement} */ (b), true);
      });
      this.addEventListener("keydown", e => this.#key(e));
      new MutationObserver(() => this.#sync()).observe(this, { childList: true });
    }
    this.#sync();
    if (typeof window.hySeg === "function") window.hySeg(this);
  }

  attributeChangedCallback() { if (this.#built) this.#sync(); }

  /** @returns {HTMLButtonElement[]} */
  options() { return /** @type {HTMLButtonElement[]} */ ([...this.children].filter(c => c.localName === "button")); }
  /** @returns {string} */
  get value() {
    const v = this.getAttribute("value");
    if (v !== null) return v;
    const o = this.options().find(b => b.classList.contains("on")) || this.options()[0];
    return o ? this.#val(o) : "";
  }
  set value(v) { this.setAttribute("value", v); }
  /** @returns {SegVariant} */
  get variant() { return oneOf(this.getAttribute("variant"), SEG_VARIANTS, "choice"); }

  /** @param {HTMLButtonElement} b */
  #val(b) { return b.value || b.getAttribute("data-v") || (b.textContent || "").trim(); }

  /**
   * @param {HTMLButtonElement} b
   * @param {boolean} person
   */
  #choose(b, person) {
    const v = this.#val(b), was = this.value;
    this.setAttribute("value", v);
    if (person) { b.focus(); if (v !== was) { this.emit("hy-change", { value: v }); this.emit("change", { value: v }); } }
  }

  /** @param {KeyboardEvent} e */
  #key(e) {
    const all = this.options().filter(b => !b.disabled);
    const i = all.findIndex(b => b === document.activeElement);
    if (i < 0) return;
    const j = segStep(e.key, i, all.length);
    if (j < 0) return;
    e.preventDefault(); this.#choose(all[j], true);
  }

  #sync() {
    const tabs = this.variant === "tabs", v = this.value, l = this.getAttribute("label");
    this.setAttribute("role", tabs ? "tablist" : "radiogroup");
    if (l) this.setAttribute("aria-label", l);
    for (const b of this.options()) {
      const on = this.#val(b) === v;
      b.type = "button";
      b.classList.toggle("on", on);
      b.setAttribute("role", tabs ? "tab" : "radio");
      b.setAttribute(tabs ? "aria-selected" : "aria-checked", String(on));
      b.removeAttribute(tabs ? "aria-checked" : "aria-selected");
      b.tabIndex = on ? 0 : -1;
    }
  }
}
define("hy-segmented", HySegmented);
