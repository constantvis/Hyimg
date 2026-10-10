// @ts-check
// <hy-split>: a button with an arrow ▾ beside it, the app's one split button (owner 2026-10-10 on round 18's Info, question 7: «Open со
// стрелкой ▾ · Preview, в приложении, в Finder, по типу файла», ★ yes, «one primitive» with «Open in <Browser> ▾»). The main part does the
// main thing; the arrow, behind a hairline, opens a menu of the other ways under the button, right edges together. <hy-open-in> is this
// element with the browsers of this Mac as its menu (ui/hy/openin.js); the Info card's Open is this element with what fits the file.
//   el.items = [{ label, short, icon, keys, main, off, run }] or () => [...] (asked each time the menu opens or the button is drawn)
//     label   the row's words; short: the main part's words when it is the main item (else its label)
//     icon    a name of the app's icons (ui/icons.js), or markup; keys: ["⇧", "⌘", "C"], the caps at the row's right end
//     main    the main part runs it, and its row says ↵ when it has no keys of its own (the board's ↵ runs the main thing)
//     sep     a line between rows instead of a row (round 19's switch-b.html: the Studio and Preview, a line, the file's rows)
//     off     the reason it does not apply now: the row stays, grey, with the reason as its tooltip (as the app's menus, ui/menu.js)
//     run     what it does; row(el, it) optional: called with the row once drawn (a row whose words come later, «Open in Preview»)
//   variant  plate (the top row's glass plate, the default) or solid (the ink pill of the Info card, 30 px)
// Keys in the open menu: ↑ ↓ walk it, ↵ or Space runs the row, Esc closes the menu and nothing else; a press elsewhere closes it.
// Events: hy-run { index } after a row or the main part ran.
import { HyElement, define, oneOf, t } from "./base.js";

/** @typedef {{ label?: string, sep?: boolean, short?: string, icon?: string, keys?: string[], main?: boolean, off?: string, run?: () => void,
 *   row?: (el: HTMLElement, it: SplitItem) => void }} SplitItem */
/** @typedef {"plate" | "solid"} SplitVariant */
/** @type {readonly SplitVariant[]} */
export const SPLIT_VARIANTS = ["plate", "solid"];

export const esc = (/** @type {string} */ s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] || c);
const ic = (/** @type {string} */ n, /** @type {number} */ s, /** @type {number} */ w, /** @type {string} */ cls = "") =>
  (typeof window.hyIcon === "function" ? window.hyIcon(n, s, w, cls) : "");

export class HySplit extends HyElement {
  static observedAttributes = ["variant"];
  /** @type {SplitItem[] | (() => SplitItem[])} */
  _items = [];
  /** @type {HTMLDivElement | null} */
  _menu = null;
  /** @type {HTMLButtonElement | null} */
  _go = null;
  /** @type {HTMLButtonElement | null} */
  _more = null;

  connectedCallback() {
    this.upgrade("items");
    if (!this._go) {
      const go = this._go = document.createElement("button"); go.type = "button"; go.className = "oi-go";
      const more = this._more = document.createElement("button"); more.type = "button"; more.className = "oi-more";
      more.setAttribute("aria-haspopup", "menu"); more.setAttribute("aria-expanded", "false"); more.setAttribute("aria-label", this.menuLabel());
      more.innerHTML = ic("chevron", 12, 2.4, "oi-cv");
      go.addEventListener("click", () => this.openHere());
      more.addEventListener("click", () => (this._menu ? this.close() : this.openMenu()));
      this.append(go, more);
    }
    this.toggleAttribute("split", true);
    this.sync();
  }

  disconnectedCallback() { this.close(); }

  /** @returns {SplitVariant} */
  get variant() { return oneOf(this.getAttribute("variant"), SPLIT_VARIANTS, "plate"); }

  /** The rows, as given (a list or a function that makes one). */
  get items() { return this._items; }
  set items(v) { this._items = v || []; if (this._go) this.sync(); }
  /** @returns {SplitItem[]} the rows now */
  list() { const v = this._items; try { return (typeof v === "function" ? v() : v) || []; } catch (e) { console.error(e); return []; } }
  /** @returns {SplitItem | null} */
  mainItem() { const L = this.list().filter(i => !i.sep); return L.find(i => i.main) || L[0] || null; }

  /** What the arrow's menu is called (a screen reader's words). */
  menuLabel() { return this.getAttribute("label") || t("More ways to open"); }

  /** The main part's words and tooltip. */
  sync() {
    const go = this._go; if (!go) return;
    const m = this.mainItem(), words = m ? m.short || m.label : "";
    // written only when it changed: the board draws its Info on every render, and the open menu keeps its rows and focus (lesson 14)
    const html = `<span>${esc(words || "")}</span>`; if (go.innerHTML !== html) go.innerHTML = html;
    go.title = this.getAttribute("tip") || (m ? `${m.label}${m.keys && m.keys.length ? " · " + m.keys.join("") : " · ↵"}` : "");
    if (this._more) this._more.title = this.menuLabel();
  }

  /** The main part: the main item. */
  openHere() { const m = this.mainItem(); if (!m || m.off) return; this.runItem(m); }

  /** @param {SplitItem} it */
  runItem(it) { const i = this.list().indexOf(it); if (it.run) it.run(); this.emit("hy-run", { index: i }); }

  /** A row of the open menu was chosen. @param {HTMLElement} row */
  choose(row) { const it = this.list()[Number(row.dataset.i)]; this.close(); if (it && !it.off) this.runItem(it); }

  openMenu() {
    if (this._menu) return;
    const m = this._menu = document.createElement("div");
    m.className = "hy-oi-menu"; m.setAttribute("role", "menu"); m.setAttribute("aria-label", this.menuLabel());
    m.addEventListener("click", e => {
      const r = /** @type {HTMLElement} */ (e.target).closest("button"); if (r instanceof HTMLElement && r.getAttribute("aria-disabled") !== "true") this.choose(r);
    });
    m.addEventListener("pointerdown", e => e.stopPropagation());
    document.body.appendChild(m); this.drawMenu();
    const r = this.getBoundingClientRect();
    m.style.top = Math.round(r.bottom + 6) + "px"; m.style.right = Math.max(8, Math.round(innerWidth - r.right)) + "px";
    if (this._more) this._more.setAttribute("aria-expanded", "true");
    addEventListener("keydown", this._key, true); addEventListener("pointerdown", this._away, true);
    const on = /** @type {HTMLElement | null} */ (m.querySelector("[aria-checked=true]") || m.querySelector("button:not([aria-disabled=true])"));
    if (on) on.focus({ preventScroll: true });
    this.opened();
  }
  /** Called once the menu is open (hy-open-in asks the app for its browsers again). */
  opened() {}

  close() {
    const m = this._menu; if (!m) return; this._menu = null; m.remove();
    if (this._more) this._more.setAttribute("aria-expanded", "false");
    removeEventListener("keydown", this._key, true); removeEventListener("pointerdown", this._away, true);
  }

  /** The menu's rows: the icon, the words, the keys at the right end (the main one's ↵). */
  drawMenu() {
    const m = this._menu; if (!m) return;
    const L = this.list();
    m.innerHTML = L.map((it, i) => {
      if (it.sep) return `<div class="oi-sep" role="separator"></div>`;
      const keys = it.keys && it.keys.length ? it.keys : it.main ? ["↵"] : [];
      const icon = it.icon ? (it.icon[0] === "<" ? it.icon : ic(it.icon, 15, 1.9, "oi-ic")) : `<span class="oi-ic"></span>`;
      return `<button type="button" role="menuitem" data-i="${i}"${it.off ? ` aria-disabled="true" title="${esc(it.off)}"` : ""}>${icon}`
        + `<span class="oi-n ml">${esc(it.label || "")}</span>${keys.length ? `<span class="oi-k">${keys.map(k => `<hy-kbd size="m">${esc(k)}</hy-kbd>`).join("")}</span>` : ""}</button>`;
    }).join("");
    m.querySelectorAll("button[data-i]").forEach(b => { const it = L[Number(/** @type {HTMLElement} */ (b).dataset.i)]; if (it && it.row) it.row(/** @type {HTMLElement} */ (b), it); });
  }

  /** Esc closes the menu and nothing else (a studio leaves on Esc); ↑ ↓ walk it, ↵ chooses; the board never sees these keys. @param {KeyboardEvent} e */
  _key = e => {
    const m = this._menu; if (!m) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); this.close(); if (this._more) this._more.focus({ preventScroll: true }); return; }
    const at = document.activeElement;
    if ((e.key === "Enter" || e.key === " ") && at instanceof HTMLButtonElement && m.contains(at)) { e.preventDefault(); e.stopImmediatePropagation(); at.click(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault(); e.stopImmediatePropagation();
    const rows = [...m.querySelectorAll("button:not([aria-disabled=true])")], i = rows.indexOf(/** @type {HTMLButtonElement} */ (document.activeElement));
    const n = /** @type {HTMLElement | undefined} */ (rows[(i + (e.key === "ArrowDown" ? 1 : rows.length - 1)) % rows.length]); if (n) n.focus({ preventScroll: true });
  };

  /** A press anywhere else closes the menu. @param {PointerEvent} e */
  _away = e => { const x = /** @type {Node} */ (e.target); if (this._menu && !this._menu.contains(x) && !(this._more && this._more.contains(x))) this.close(); };

  attributeChangedCallback() { if (this._go) this.sync(); }
}
define("hy-split", HySplit);
