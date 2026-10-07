// @ts-check
// <hy-hint>a footnote with the <b>key words</b></hy-hint> and <hy-info tip="…"> (ui/hy/hint.css): the app's only ways to explain
// (owner 2026-10-06). hy-hint is text and nothing else. hy-info is a ⓘ the keyboard reaches: its explanation is its tooltip (title, or
// data-tip on a page with its own tooltips, the image studio) and what VoiceOver reads; Enter or Space sends hy-info { tip } for a page
// that shows it in place.
import { HyElement, define, t } from "./base.js";

export class HyHint extends HyElement {}
define("hy-hint", HyHint);

export class HyInfo extends HyElement {
  static observedAttributes = ["tip"];
  #built = false;

  connectedCallback() {
    this.upgrade("tip");
    if (!this.#built) {
      this.#built = true;
      this.setAttribute("role", "button");
      if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
      this.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.emit("hy-info", { tip: this.tip }); } });
      this.addEventListener("click", () => this.emit("hy-info", { tip: this.tip }));
    }
    this.#sync();
  }

  attributeChangedCallback() { if (this.#built) this.#sync(); }

  /** @returns {string} */
  get tip() { return this.getAttribute("tip") || ""; }
  set tip(v) { this.setWord("tip", v || null); }

  #sync() {
    const tip = this.tip;
    this.setAttribute("aria-label", tip || t("More information"));
    if (this.hasAttribute("data-tip")) this.setAttribute("data-tip", tip); else if (tip) this.title = tip; else this.removeAttribute("title");
  }
}
define("hy-info", HyInfo);
