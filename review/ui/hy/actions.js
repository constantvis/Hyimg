// @ts-check
// <hy-studio-actions>: a Studio's session actions, the buttons that end or steer the session (Save, Cancel, Done, Reload, Open in <Browser>).
// Owner 2026-10-09 on Dev Studio's dock, where Reload, Open and Done stood beside the tools: «кнопки Done у нас всегда стандартизированы
// справа вверху, а не внизу ... Их тоже нужно систематизировать, чтобы они везде были идентичны». One element for Image Studio, 3D Studio,
// Dev Studio and the HTML frame's live view. It stands in the top row at its right end: in a Studio at the row's gutter, the round buttons
// are away there (ui/modes.js, owner 2026-10-09: «В режиме студии мы вот эти все элементы убираем»); elsewhere (the HTML frame's live
// view on the board) just left of the round buttons that show, the row's gap apart. Each action is a plate of the row
// (<hy-button size=plate>); the secondary ones in the order given, the one primary last, filled with the colour of where it stands
// (--sel: a Studio's own colour inside its root) with white words and a check.
//   const a = document.createElement("hy-studio-actions"); studioRoot.append(a);
//   a.actions = [{ id: "reload", label: "Reload", tip: "Reload the page", key: "⌘R" }, { id: "open", open: () => url, tip: "…" },
//                { id: "done", label: "Done", tip: "Done", key: "Esc", primary: true, run: close }]
// A click runs the action's run() and sends hy-action {id}; every button carries data-a=<id>, so a studio that reads clicks on its root by
// data-a keeps doing so. The tooltip is the page's kind: title="Done · Esc" (or the action's whole title) on the board, data-tip and
// data-key in Image Studio's page (tips="data"). key= is also the button's key cap, shown while ⌘ is held (ui/keyhints.js); the keys
// themselves stay the studio's. An action with open: is the split button «Open in <Browser>» (ui/hy/openin.js). The element carries
// data-hyui, so ⌘. hides it with the rest of the interface.
import { HyElement, define, t, icon } from "./base.js";
import "./button.js";
import "./openin.js";

/**
 * @typedef {object} StudioAction
 * @property {string} id the button's data-a
 * @property {string} [label] its words
 * @property {string} [tip] what it does, the tooltip before its key
 * @property {string} [title] the whole tooltip as one string (a studio's translated «Save … · ⌘↵»), instead of tip and key
 * @property {string} [key] the key that does it, shown in the tooltip and as the key cap under ⌘
 * @property {boolean} [primary] the session's main action: last, in the studio's colour; one per list
 * @property {boolean} [disabled]
 * @property {() => void} [run]
 * @property {() => string} [open] the address to open: the action is «Open in <Browser>»
 */

/** The row's round buttons the actions stand left of: the board's, then Image Studio's page (its gear only). */
export const BESIDE = "#bntf, #bkeys, #bhist, #bset";

/**
 * A tooltip in the page's kind.
 * @param {HTMLElement} el
 * @param {string} tip
 * @param {string | undefined} key
 * @param {string | undefined} whole
 * @param {boolean} data
 */
export function tipOn(el, tip, key, whole, data) {
  if (data) {
    el.dataset.tip = whole || tip; el.dataset.side = "bottom";
    if (key) el.dataset.key = key; else delete el.dataset.key;
    el.removeAttribute("title");
  } else el.title = whole || (key ? `${tip} · ${key}` : tip);
}

export class HyStudioActions extends HyElement {
  /** @type {StudioAction[]} */
  #list = [];
  /** @type {MutationObserver | null} */
  #mo = null;
  #later = 0;
  #placeNow = () => this.place();

  connectedCallback() {
    this.upgrade("actions");
    this.setAttribute("role", "toolbar"); this.setAttribute("data-hyui", "");
    if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", t("Studio actions"));
    addEventListener("resize", this.#placeNow);
    // the round buttons move when the row changes: the merge's face slides the bell and the keys (ui/merge.css), the look resizes them
    this.#mo = new MutationObserver(() => { this.place(); clearTimeout(this.#later); this.#later = window.setTimeout(this.#placeNow, 450); });
    // and go away in a Studio (ui/modes.js data-in-studio): the actions then stand at the row's gutter
    this.#mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-ui", "data-shape", "data-in-studio"] });
    this.draw(); this.place(); requestAnimationFrame(this.#placeNow);
  }

  disconnectedCallback() { removeEventListener("resize", this.#placeNow); if (this.#mo) this.#mo.disconnect(); clearTimeout(this.#later); }

  /** @returns {StudioAction[]} */
  get actions() { return this.#list.slice(); }
  set actions(v) { this.#list = Array.isArray(v) ? v.slice() : []; if (this.isConnected) { this.draw(); this.place(); } }

  /**
   * The element of one action (a <hy-button>, or the <hy-open-in>).
   * @param {string} id
   * @returns {HTMLElement | null}
   */
  button(id) { return /** @type {HTMLElement | null} */ (this.querySelector(`:scope > [data-a="${CSS.escape(id)}"]`)); }

  /**
   * Turns one action on or off (a studio busy saving).
   * @param {string} id
   * @param {boolean} off
   */
  disable(id, off) { const b = this.button(id); if (b) b.toggleAttribute("disabled", !!off); }

  /** @private */
  draw() {
    const data = this.getAttribute("tips") === "data";
    const list = [...this.#list.filter(a => !a.primary), ...this.#list.filter(a => a.primary).slice(0, 1)];   // one primary, rightmost
    this.replaceChildren(...list.map(a => {
      if (a.open) {
        const o = /** @type {import("./openin.js").HyOpenIn} */ (document.createElement("hy-open-in"));
        o.dataset.a = a.id; o.target = a.open; o.tip = a.tip || ""; if (data) o.setAttribute("tips", "data");
        o.addEventListener("hy-open", () => this.emit("hy-action", { id: a.id }));
        return o;
      }
      const b = document.createElement("hy-button");
      b.setAttribute("size", "plate"); b.dataset.a = a.id;
      if (a.primary) b.setAttribute("variant", "accent");
      if (a.key) b.setAttribute("kbd", a.key);
      if (a.disabled) b.setAttribute("disabled", "");
      const words = document.createElement("span"); words.textContent = a.label || a.id;
      if (a.primary) b.insertAdjacentHTML("afterbegin", icon("check", 14, 2.4));
      b.append(words);
      tipOn(b, a.tip || a.label || "", a.key, a.title, data);
      b.addEventListener("click", () => {
        if (b.hasAttribute("disabled")) return;
        if (a.run) a.run();
        this.emit("hy-action", { id: a.id });
      });
      return b;
    }));
  }

  /** Stands the row's gap left of the round buttons that show, else the row's gutter from the window's edge. */
  place() {
    if (!this.isConnected) return;
    const root = getComputedStyle(document.documentElement);
    const gap = parseFloat(root.getPropertyValue("--hy-row-gap")) || 8, gut = parseFloat(root.getPropertyValue("--hy-row-gut")) || 12;
    let left = Infinity;
    for (const e of document.querySelectorAll(this.getAttribute("beside") || BESIDE)) {
      if (!(e instanceof HTMLElement) || this.contains(e) || !e.getClientRects().length) continue;
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      if (!r.width || s.visibility === "hidden" || r.top > 40) continue;   // only the row's: a button that moved away is not in it
      left = Math.min(left, r.left);
    }
    this.style.right = (left === Infinity ? gut : Math.max(gut, Math.round(innerWidth - left + gap))) + "px";
  }
}
define("hy-studio-actions", HyStudioActions);
