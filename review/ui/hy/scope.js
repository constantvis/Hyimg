// @ts-check
// <hy-scope shown="22" total="87" all label="…">: round 15's count as the scope (owner 2026-10-09 on r15-micro.html, control 2; «Все топ,
// все делай»; ui/hy/scope.css). The count «22 / 87» is itself the switch: a click shows every one of the total (all, the count reads
// «87 / 87» on a grey plate) and a second click goes back to the part; the page fills shown (the part) and total and listens to
// hy-change { all }. It sits at the end of a search field (the 3D outliner's 22 of 87 nodes). A real button inside, so a click on it in a
// <label> does not move to the label's field; aria-pressed says the state, its label and title say both numbers.
import { HyElement, define, t } from "./base.js";

/**
 * A count's digits: a whole number, nothing for what is not one.
 * @param {string | null} v
 * @returns {string}
 */
export function scopeNum(v) {
  const n = Number(v);
  return v === null || v.trim() === "" || !Number.isFinite(n) ? "" : String(Math.max(0, Math.round(n)));
}

export class HyScope extends HyElement {
  static observedAttributes = ["shown", "total", "all", "label", "disabled"];
  /** @type {HTMLButtonElement | null} */
  #btn = null;

  connectedCallback() {
    this.upgrade("all");
    if (!this.#btn) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "hy-scope-b";
      b.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); this.toggle(); });
      this.replaceChildren(b);
      this.#btn = b;
    }
    this.#sync();
  }

  attributeChangedCallback() { this.#sync(); }

  /** @returns {boolean} */
  get all() { return this.flag("all"); }
  set all(v) { this.setFlag("all", v); }
  /** The button inside (null before the element is in a document). */
  get button() { return this.#btn; }

  /**
   * Shows all, or the shown part again (or `force`), as the person's click does: hy-change follows when it changes.
   * @param {boolean} [force]
   */
  toggle(force) {
    const v = force === undefined ? !this.all : !!force;
    if (v === this.all || this.flag("disabled")) return;
    this.all = v; this.emit("hy-change", { all: v });
  }

  focus() { this.#btn ? this.#btn.focus() : super.focus(); }

  #sync() {
    const b = this.#btn; if (!b) return;
    const shown = scopeNum(this.getAttribute("shown")), total = scopeNum(this.getAttribute("total"));
    b.innerHTML = total ? `${this.all ? total : shown || "0"}<i>/</i>${total}` : shown;
    b.disabled = this.flag("disabled");
    b.setAttribute("aria-pressed", String(this.all));
    const l = this.getAttribute("label") || (total ? t(this.all ? "All {total} shown · show only {shown}" : "{shown} of {total} shown · show all", { shown: shown || "0", total }) : "");
    if (l) { b.setAttribute("aria-label", l); b.title = l; } else { b.removeAttribute("aria-label"); b.removeAttribute("title"); }
  }
}
define("hy-scope", HyScope);
