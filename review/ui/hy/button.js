// @ts-check
// <hy-button variant="plain|solid|ghost|danger|reset|accent" size="s|m|l|row|dock|plate" icon="name" kbd="⌘S" pressed toggle disabled>Words</hy-button>
// and <hy-icon-button icon="close" label="Close" size="xs|s|m|l|dock|plate" variant="ghost|plain|solid|danger|reset" shape="round|square"
// pressed toggle disabled> (ui/hy/button.css). Each keeps a real <button> inside that fills it: the keyboard, the focus, VoiceOver, a
// page's click listener on the element, menu.js and keyhints.js (kbd= becomes the button's own <kbd>, shown under ⌘) all work through it.
// toggle: a click turns pressed over and sends hy-toggle { pressed }. disabled: the button inside is disabled, no click comes out.
import { HyElement, define, oneOf, icon } from "./base.js";

/** @typedef {"plain" | "solid" | "ghost" | "danger" | "reset" | "accent"} ButtonVariant */
/** @typedef {"xs" | "s" | "m" | "l" | "row" | "dock" | "plate"} ButtonSize */
/** @type {readonly ButtonVariant[]} */
export const BUTTON_VARIANTS = ["plain", "solid", "ghost", "danger", "reset", "accent"];
/** @type {readonly ButtonSize[]} */
export const BUTTON_SIZES = ["xs", "s", "m", "l", "row", "dock", "plate"];
/** The height of each size in px (ui/tokens.css --hy-h-*), and the icon drawn in it. */
export const BUTTON_PX = /** @type {const} */ ({ xs: 20, s: 24, m: 28, l: 30, row: 32, dock: 34, plate: 38 });
export const ICON_PX = /** @type {const} */ ({ xs: 12, s: 14, m: 16, l: 16, row: 16, dock: 18, plate: 18 });

class HyButtonBase extends HyElement {
  static observedAttributes = ["pressed", "disabled", "icon", "kbd", "label", "size"];
  /** @type {HTMLButtonElement | null} */
  #btn = null;

  connectedCallback() {
    this.upgrade("pressed", "disabled", "variant", "size");
    if (!this.#btn) {
      const b = document.createElement("button");
      b.type = "button";
      while (this.firstChild) b.appendChild(this.firstChild);
      this.appendChild(b);
      this.#btn = b;
      b.addEventListener("click", () => {
        if (!this.hasAttribute("toggle") || this.disabled) return;
        this.pressed = !this.pressed;
        this.emit("hy-toggle", { pressed: this.pressed });
      });
    }
    this.sync();
  }

  attributeChangedCallback() { if (this.#btn) this.sync(); }

  /** The real button inside (null before the element is in a document). */
  get button() { return this.#btn; }
  /** @returns {boolean} */
  get pressed() { return this.flag("pressed"); }
  set pressed(v) { this.setFlag("pressed", v); }
  /** @returns {boolean} */
  get disabled() { return this.flag("disabled"); }
  set disabled(v) { this.setFlag("disabled", v); }
  /** @returns {ButtonVariant} */
  get variant() { return oneOf(this.getAttribute("variant"), BUTTON_VARIANTS, this.localName === "hy-icon-button" ? "ghost" : "plain"); }
  set variant(v) { this.setWord("variant", oneOf(v, BUTTON_VARIANTS, "plain")); }
  /** @returns {ButtonSize} */
  get size() { return oneOf(this.getAttribute("size"), BUTTON_SIZES, "m"); }
  set size(v) { this.setWord("size", v === "m" ? null : oneOf(v, BUTTON_SIZES, "m")); }

  focus() { this.#btn ? this.#btn.focus() : super.focus(); }
  click() { this.#btn ? this.#btn.click() : super.click(); }

  /** @protected */
  sync() {
    const b = this.#btn; if (!b) return;
    b.disabled = this.disabled;
    if (this.hasAttribute("toggle") || this.hasAttribute("pressed")) b.setAttribute("aria-pressed", String(this.pressed)); else b.removeAttribute("aria-pressed");
    this.drawIcon(b);
    const k = this.getAttribute("kbd");
    let kb = b.querySelector(":scope > kbd.hy-k");
    if (k) { if (!kb) { kb = document.createElement("kbd"); kb.className = "hy-k"; b.appendChild(kb); } kb.textContent = k; }
    else if (kb) kb.remove();
  }

  /**
   * The icon of the icon= attribute, first in the button, at the size's icon size.
   * @protected
   * @param {HTMLButtonElement} b
   */
  drawIcon(b) {
    const name = this.getAttribute("icon") || "";
    const old = b.querySelector(":scope > svg.hy-i");
    const want = name ? `${name}@${ICON_PX[this.size]}` : "";
    if (old && old.getAttribute("data-k") === want) return;
    if (old) old.remove();
    if (!want) return;
    b.insertAdjacentHTML("afterbegin", icon(name, ICON_PX[this.size]));
    const svg = b.firstElementChild;
    if (svg && svg.localName === "svg") { svg.classList.add("hy-i"); svg.setAttribute("data-k", want); }
  }
}

export class HyButton extends HyButtonBase {}
define("hy-button", HyButton);

export class HyIconButton extends HyButtonBase {
  /** @protected */
  sync() {
    super.sync();
    const b = this.button; if (!b) return;
    const l = this.getAttribute("label") || "";
    if (l) { b.setAttribute("aria-label", l); if (!this.hasAttribute("data-tip")) b.title = l; }
  }
}
define("hy-icon-button", HyIconButton);
