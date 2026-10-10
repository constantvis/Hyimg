// @ts-check
// <hy-led state="on|ok|off|busy|err" label="…">: round 15's status LED (owner 2026-10-09 on r15-micro.html, control 4: «Все топ, все
// делай»; ui/hy/led.css). 6 px, flat, no glow. on: the selection's colour, which is the Studio's inside a Studio (3D pink, Image purple,
// Dev green; the current camera, a Studio's job done); ok: green, «running» on the board and in Settings; off: a ring; busy: the on colour
// blinking, only while something works; err: red, a write refused (Dev Studio's file, P4 S-39). Drawn from the attribute alone (Home loads
// no modules); the script gives it role img and the label as its name, or hides it from VoiceOver when the row beside it says it.
import { HyElement, define, oneOf } from "./base.js";

/** @typedef {"on" | "ok" | "off" | "busy" | "err"} LedState */
/** @type {readonly LedState[]} */
export const LED_STATES = ["on", "ok", "off", "busy", "err"];

export class HyLed extends HyElement {
  static observedAttributes = ["state", "label", "title"];

  connectedCallback() { this.#sync(); }
  attributeChangedCallback() { this.#sync(); }

  /** @returns {LedState} */
  get state() { return oneOf(this.getAttribute("state"), LED_STATES, "on"); }
  set state(v) { this.setWord("state", v === "on" ? null : v); }

  #sync() {
    const l = this.getAttribute("label") || this.getAttribute("title");
    if (l) { this.setAttribute("role", "img"); this.setAttribute("aria-label", l); this.removeAttribute("aria-hidden"); }
    else { this.removeAttribute("role"); this.removeAttribute("aria-label"); this.setAttribute("aria-hidden", "true"); }
  }
}
define("hy-led", HyLed);
