// @ts-check
// <hy-badge count="3" tone="sel|red|neutral" dot zero label="…">: a count on a button's corner, or a dot (ui/hy/badge.css). count fills
// its words (more than 99 is «99+»); a count of 0 hides it unless zero is set; label is what VoiceOver says («3 new»).
import { HyElement, define, oneOf } from "./base.js";

/** @typedef {"sel" | "red" | "neutral"} BadgeTone */
/** @type {readonly BadgeTone[]} */
export const BADGE_TONES = ["sel", "red", "neutral"];

/**
 * The words of a count: digits, «99+» above 99, nothing for a value that is not a number.
 * @param {string | null} v
 * @returns {string}
 */
export function badgeText(v) {
  if (v === null || v.trim() === "") return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  return n > 99 ? "99+" : String(Math.max(0, Math.round(n)));
}

export class HyBadge extends HyElement {
  static observedAttributes = ["count", "label", "dot"];

  connectedCallback() { this.#sync(); }
  attributeChangedCallback() { this.#sync(); }

  /** @returns {number} */
  get count() { const n = Number(this.getAttribute("count")); return Number.isFinite(n) ? n : 0; }
  set count(v) { this.setAttribute("count", String(v)); }
  /** @returns {BadgeTone} */
  get tone() { return oneOf(this.getAttribute("tone"), BADGE_TONES, "sel"); }
  set tone(v) { this.setWord("tone", v === "sel" ? null : v); }

  #sync() {
    if (this.hasAttribute("count") && !this.flag("dot")) this.textContent = badgeText(this.getAttribute("count"));
    const l = this.getAttribute("label");
    if (l) { this.setAttribute("role", "status"); this.setAttribute("aria-label", l); }
    else if (this.flag("dot")) this.setAttribute("aria-hidden", "true");
  }
}
define("hy-badge", HyBadge);
