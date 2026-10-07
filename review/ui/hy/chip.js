// @ts-check
// <hy-chip state="off|include|exclude" cycle="three|two" count="12" pinned disabled>Words</hy-chip>: a filter (ui/hy/chip.css). A click
// or Enter / Space moves it on: off → include → exclude → off (cycle=two: off ↔ include), as the library's filters do. hy-change
// { state } follows; aria-pressed says it to VoiceOver (true included, mixed left out).
import { HyElement, define, oneOf, icon } from "./base.js";

/** @typedef {"off" | "include" | "exclude"} ChipState */
/** @type {readonly ChipState[]} */
export const CHIP_STATES = ["off", "include", "exclude"];

/**
 * The state after a press.
 * @param {ChipState} s
 * @param {boolean} two  only off and include
 * @returns {ChipState}
 */
export function nextChipState(s, two) {
  if (two) return s === "off" ? "include" : "off";
  return s === "off" ? "include" : s === "include" ? "exclude" : "off";
}

export class HyChip extends HyElement {
  static observedAttributes = ["state", "count", "pinned", "disabled"];
  #built = false;

  connectedCallback() {
    this.upgrade("state");
    if (!this.#built) {
      this.#built = true;
      const lbl = document.createElement("span"); lbl.className = "hy-lbl";
      while (this.firstChild) lbl.appendChild(this.firstChild);
      this.appendChild(lbl);
      if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
      this.setAttribute("role", "button");
      this.addEventListener("click", () => this.press());
      this.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.press(); } });
    }
    this.#sync();
  }

  attributeChangedCallback() { if (this.#built) this.#sync(); }

  /** @returns {ChipState} */
  get state() { return oneOf(this.getAttribute("state"), CHIP_STATES, "off"); }
  set state(v) { this.setWord("state", v === "off" ? null : oneOf(v, CHIP_STATES, "off")); }

  /** The person's press: the next state and hy-change. */
  press() {
    if (this.flag("disabled")) return;
    this.state = nextChipState(this.state, this.getAttribute("cycle") === "two");
    this.emit("hy-change", { state: this.state });
  }

  #sync() {
    const s = this.state;
    this.setAttribute("aria-pressed", s === "include" ? "true" : s === "exclude" ? "mixed" : "false");
    this.setAttribute("aria-disabled", String(this.flag("disabled")));
    let n = this.querySelector(":scope > .hy-n");
    const c = this.getAttribute("count");
    if (c !== null && c !== "") { if (!n) { n = document.createElement("span"); n.className = "hy-n"; this.appendChild(n); } n.textContent = c; }
    else if (n) n.remove();
    let pin = this.querySelector(":scope > .hy-pin");
    if (this.flag("pinned")) { if (!pin) { this.insertAdjacentHTML("afterbegin", icon("pin", 13, 2)); pin = this.firstElementChild; if (pin) pin.classList.add("hy-pin"); } }
    else if (pin) pin.remove();
  }
}
define("hy-chip", HyChip);
