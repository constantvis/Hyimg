// @ts-check
// <hy-kbd size="s|m|l" quiet>⌘</hy-kbd>: a key cap (ui/hy/kbd.css). Nothing to press: the element only keeps its size word valid.
import { HyElement, define, oneOf } from "./base.js";

/** @typedef {"s" | "m" | "l"} KbdSize */
/** @type {readonly KbdSize[]} */
export const KBD_SIZES = ["s", "m", "l"];

export class HyKbd extends HyElement {
  /** @returns {KbdSize} */
  get size() { return oneOf(this.getAttribute("size"), KBD_SIZES, "l"); }
  /** @param {KbdSize} v */
  set size(v) { this.setWord("size", v === "l" ? null : oneOf(v, KBD_SIZES, "l")); }
}
define("hy-kbd", HyKbd);
