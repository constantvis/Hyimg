// @ts-check
// <hy-minitoggle checked disabled label="…">All nodes</hy-minitoggle>: round 15's mini toggle (owner 2026-10-09 on r15-micro.html: «Все топ,
// все делай»; ui/hy/minitoggle.css). A 20 × 11 track with an 8 px knob and its words at 11 px, 22 px tall: an option that lives in a row of
// something else (the 3D outliner's «All nodes» beside its search, an inspector's «Visible»), where hy-switch's 30 × 18 is too loud. Without
// words it is the track alone (a row's label says what it is). As hy-switch: a real checkbox with role=switch lies over it (24 px tall, the
// contract's smallest target), Space and Enter toggle it, hy-change { checked } follows each change the person makes, not one made by code.
import { HyElement, define } from "./base.js";

export class HyMiniToggle extends HyElement {
  static observedAttributes = ["checked", "disabled", "label"];
  /** @type {HTMLInputElement | null} */
  #input = null;

  connectedCallback() {
    this.upgrade("checked", "disabled");
    if (!this.#input) {
      const i = document.createElement("input");
      i.type = "checkbox"; i.className = "hy-in"; i.setAttribute("role", "switch");
      i.addEventListener("change", () => { this.checked = i.checked; this.emit("hy-change", { checked: i.checked }); });
      i.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); i.click(); } });
      this.prepend(i);
      this.#input = i;
    }
    this.#sync();
  }

  attributeChangedCallback() { this.#sync(); }

  /** @returns {boolean} */
  get checked() { return this.flag("checked"); }
  set checked(v) { this.setFlag("checked", v); }
  /** @returns {boolean} */
  get disabled() { return this.flag("disabled"); }
  set disabled(v) { this.setFlag("disabled", v); }
  /** The checkbox inside (null before the element is in a document). */
  get input() { return this.#input; }
  /** Its words, without the checkbox. @returns {string} */
  get text() { return [...this.childNodes].filter(n => n !== this.#input).map(n => n.textContent || "").join("").trim(); }

  /**
   * Turns it over (or to `force`) as the person would: hy-change follows when the state changes.
   * @param {boolean} [force]
   */
  toggle(force) {
    const v = force === undefined ? !this.checked : !!force;
    if (v === this.checked || this.disabled) return;
    this.checked = v; this.emit("hy-change", { checked: v });
  }

  focus() { this.#input ? this.#input.focus() : super.focus(); }

  #sync() {
    const i = this.#input; if (!i) return;
    i.checked = this.checked; i.disabled = this.disabled;
    const words = this.text;
    this.toggleAttribute("bare", !words);
    const l = this.getAttribute("label") || words;
    if (l) i.setAttribute("aria-label", l); else i.removeAttribute("aria-label");
  }
}
define("hy-minitoggle", HyMiniToggle);
