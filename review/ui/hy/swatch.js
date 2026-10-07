// @ts-check
// <hy-swatch color="#f4c430" | color="--note" selected none size="m" label="Yellow"> and <hy-swatches value="…"> (ui/hy/swatch.css).
// Alone a swatch is a toggle button (aria-pressed). In <hy-swatches> the row is one choice (radiogroup): a click or ← → picks, hy-change
// { value, color } follows from the row, value is the chosen swatch's value (its value attribute, else its colour; "" for none).
import { HyElement, define } from "./base.js";

/**
 * The CSS value of a colour attribute: a token's name becomes var(--name).
 * @param {string | null} c
 * @returns {string}
 */
export function swatchColor(c) {
  if (!c) return "";
  return /^--[\w-]+$/.test(c) ? `var(${c})` : c;
}

/**
 * A swatch's value from its attributes (it may not be upgraded yet): value=, else "" for none, else its colour.
 * @param {Element} s
 * @returns {string}
 */
export function valueOf(s) { return s.getAttribute("value") ?? (s.hasAttribute("none") ? "" : s.getAttribute("color") || ""); }

export class HySwatch extends HyElement {
  static observedAttributes = ["color", "selected", "label", "none", "disabled"];
  #built = false;

  connectedCallback() {
    this.upgrade("selected");
    if (!this.#built) {
      this.#built = true;
      if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
      this.addEventListener("click", () => this.pick());
      this.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.pick(); } });
    }
    this.#sync();
  }

  attributeChangedCallback() { if (this.#built) this.#sync(); }

  /** @returns {boolean} */
  get selected() { return this.flag("selected"); }
  set selected(v) { this.setFlag("selected", v); }
  /** @returns {string} */
  get value() { return valueOf(this); }

  /** The person's pick: in a row the row chooses it, alone it turns over. */
  pick() {
    if (this.flag("disabled")) return;
    const row = this.closest("hy-swatches");
    if (row instanceof HySwatches) { row.choose(this, true); return; }
    this.selected = !this.selected; this.emit("hy-change", { selected: this.selected, value: this.value });
  }

  #sync() {
    this.style.setProperty("--hy-sw", swatchColor(this.getAttribute("color")));
    const inRow = !!this.closest("hy-swatches");
    this.setAttribute("role", inRow ? "radio" : "button");
    this.setAttribute(inRow ? "aria-checked" : "aria-pressed", String(this.selected));
    this.removeAttribute(inRow ? "aria-pressed" : "aria-checked");
    const l = this.getAttribute("label") || this.getAttribute("color") || "";
    if (l) { this.setAttribute("aria-label", l); if (!this.title) this.title = l; }
    if (inRow) this.tabIndex = this.selected ? 0 : -1;
  }
}
define("hy-swatch", HySwatch);

export class HySwatches extends HyElement {
  #built = false;

  connectedCallback() {
    this.setAttribute("role", "radiogroup");
    if (!this.#built) { this.#built = true; this.addEventListener("keydown", e => this.#key(e)); }
    // the row connects before its swatches are upgraded (they come after it in the markup): it reads and sets their attributes only
    const v = this.getAttribute("value");
    const all = this.swatches();
    const pick = v !== null ? all.find(s => valueOf(s) === v) : all.find(s => s.hasAttribute("selected"));
    if (pick) this.choose(pick, false);
  }

  /** @returns {HTMLElement[]} */
  swatches() { return [...this.querySelectorAll("hy-swatch")].filter(s => !s.hasAttribute("disabled")); }
  /** @returns {string} */
  get value() { const s = this.swatches().find(x => x.hasAttribute("selected")); return s ? valueOf(s) : ""; }
  set value(v) { const s = this.swatches().find(x => valueOf(x) === v); if (s) this.choose(s, false); }

  /**
   * @param {HTMLElement} sw
   * @param {boolean} person  true: the person picked it, hy-change follows
   */
  choose(sw, person) {
    const was = this.value;
    for (const s of this.swatches()) { s.toggleAttribute("selected", s === sw); s.tabIndex = s === sw ? 0 : -1; }
    this.setAttribute("value", valueOf(sw));
    if (person) { sw.focus(); if (valueOf(sw) !== was) this.emit("hy-change", { value: valueOf(sw), color: sw.getAttribute("color") || "" }); }
  }

  /** @param {KeyboardEvent} e */
  #key(e) {
    const all = this.swatches(); if (!all.length) return;
    const cur = all.findIndex(s => s === document.activeElement);
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    let i = -1;
    if (step) i = ((cur < 0 ? 0 : cur) + step + all.length) % all.length;
    else if (e.key === "Home") i = 0; else if (e.key === "End") i = all.length - 1;
    if (i < 0) return;
    e.preventDefault(); this.choose(all[i], true);
  }
}
define("hy-swatches", HySwatches);
