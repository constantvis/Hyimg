// @ts-check
// <hy-switch checked disabled label="…">: on or off (ui/hy/switch.css). A real checkbox with role=switch lies over the track: Space and
// Enter toggle it, a <label> around the switch toggles it, VoiceOver reads it. Events: the checkbox's own input and change bubble out of
// the element, and hy-change { checked } follows each change made by the person (not one made by code). static: a switch that only shows
// a state, inside a row that toggles it (a menu item): no checkbox of its own, hidden from VoiceOver, the row says it.
import { HyElement, define } from "./base.js";

export class HySwitch extends HyElement {
  static observedAttributes = ["checked", "disabled", "label"];
  /** @type {HTMLInputElement | null} */
  #input = null;

  connectedCallback() {
    this.upgrade("checked", "disabled");
    if (this.hasAttribute("static")) { this.setAttribute("aria-hidden", "true"); return; }
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
    const l = this.getAttribute("label");
    if (l) i.setAttribute("aria-label", l); else i.removeAttribute("aria-label");
  }
}
define("hy-switch", HySwitch);
