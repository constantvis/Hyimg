// @ts-check
// <hy-plate kind="title|capsule" place="row-left|row-right">: a plate of the top row (ui/hy/plate.css). Its look is the row's; the
// element only keeps its words valid (the board's stuck group title is one: canvas.html .gst, class hy-plate kept for the row's checks).
import { HyElement, define, oneOf } from "./base.js";

/** @typedef {"title" | "capsule"} PlateKind */
/** @type {readonly PlateKind[]} */
export const PLATE_KINDS = ["title", "capsule"];

export class HyPlate extends HyElement {
  /** @returns {PlateKind} */
  get kind() { return oneOf(this.getAttribute("kind"), PLATE_KINDS, "title"); }
  set kind(v) { this.setWord("kind", v === "title" ? null : v); }
}
define("hy-plate", HyPlate);
