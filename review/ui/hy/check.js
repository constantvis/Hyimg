// @ts-check
// <hy-check checked indeterminate disabled>Words</hy-check>: a checkbox with its words (ui/hy/check.css). A real checkbox lies over the
// whole element: a click on the words ticks it, Space toggles it, VoiceOver reads the words. Events: input and change bubble from the
// checkbox, hy-change { checked } follows each change made by the person. A click on an indeterminate box makes it checked.
import { HyElement, define } from "./base.js";

/** The bar of an indeterminate box: the registry's «minus» as a CSS image (as ui/icons.js puts --hy-ic-check-on). */
function minusImage() {
  if (document.getElementById("hy-ic-hy") || typeof window.hyIconURL !== "function") return;
  const st = document.createElement("style"); st.id = "hy-ic-hy";
  st.textContent = `:root { --hy-ic-minus-on: ${window.hyIconURL("minus", "white", 3.4)}; }`;
  (document.head || document.documentElement).appendChild(st);
}

export class HyCheck extends HyElement {
  static observedAttributes = ["checked", "indeterminate", "disabled", "label"];
  /** @type {HTMLInputElement | null} */
  #input = null;

  connectedCallback() {
    this.upgrade("checked", "indeterminate", "disabled");
    minusImage();
    if (!this.#input) {
      const i = document.createElement("input");
      i.type = "checkbox"; i.className = "hy-in";
      i.addEventListener("change", () => {
        const v = i.checked;   // first: each attribute set below syncs the box from the attributes
        this.checked = v; this.indeterminate = false;
        this.emit("hy-change", { checked: v });
      });
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
  get indeterminate() { return this.flag("indeterminate"); }
  set indeterminate(v) { this.setFlag("indeterminate", v); }
  /** @returns {boolean} */
  get disabled() { return this.flag("disabled"); }
  set disabled(v) { this.setFlag("disabled", v); }
  get input() { return this.#input; }

  focus() { this.#input ? this.#input.focus() : super.focus(); }

  #sync() {
    const i = this.#input; if (!i) return;
    i.checked = this.checked; i.indeterminate = this.indeterminate; i.disabled = this.disabled;
    const l = this.getAttribute("label") || (this.textContent || "").trim();
    if (l) i.setAttribute("aria-label", l); else i.removeAttribute("aria-label");
  }
}
define("hy-check", HyCheck);
