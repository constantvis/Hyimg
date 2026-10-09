// @ts-check
// <hy-open-in>: «Open in <Browser>», a split button of the top row (owner 2026-10-09 on Dev Studio's «Open»: «Что такое Open? Может быть,
// Open in browser тогда нужно написать. И также добавить логотип, какой у нас стандартный браузер ... Либо, может быть, еще такую кнопку со
// стрелочкой, чтобы выбрать браузер, в котором открывать, и там, соответственно, тоже логотип браузера»).
// In the Mac app: the main part reads «Open in Safari» with Safari's own icon and opens the page there; the chevron opens a menu of the
// browsers on this Mac, each with its icon and name, the system's default marked; choosing one opens the page in it, and it stays the main
// part's browser from then on (the app remembers it for this Mac's user). Elsewhere (a plain browser, or an app built before the browsers
// existed, which never answers): «Open in browser», no icon, the page in a new tab; the button keeps its shape, the chevron and its
// hairline, and the menu has the one row it can offer, «Default browser» (owner 2026-10-09 on the plain form: «Ты не добавил стрелочки
// у этой кнопки, которая имеет разделитель вертикальный, чтобы можно было выбрать браузер»).
// The app's side (native/Browsers.swift): the page sends {action: "browsers", op: "list"} and gets window.hyimgBrowsers({op: "list",
// browsers: [{id, name, icon}], default, last}); {op: "open", url, app} opens the url in that browser and answers {op: "open", app} or
// {op: "open", error}. window.hyBrowsers is this way for the classic scripts; hyBrowsers.via(fn) puts another one in (the tests).
// A studio sets el.target = () => url (and el.tip, the tooltip of the plain form); the element sends hy-open when it opened something.
import { HyElement, define, t } from "./base.js";

/** @typedef {{ id: string, name: string, icon: string }} Browser */
/** @typedef {{ browsers: Browser[], default: string, last: string }} Browsers */
/** @typedef {(m: Record<string, unknown>) => boolean} Send */

/** @type {{ got: Browsers | null, via: Send | null, subs: Set<() => void> }} */
const B = { got: null, via: null, subs: new Set() };

/** The Mac app's message port, or null in a plain browser: WKWebView's handler (the board's frame posts through the top window), CEF's log. */
function appPort() {
  /** @type {any} */ let wk = null;
  try { const w = /** @type {any} */ (window.top || window).webkit || /** @type {any} */ (window).webkit; wk = w && w.messageHandlers && w.messageHandlers.hyimg; } catch { wk = null; }
  if (wk) return /** @type {Send} */ (m => { wk.postMessage(m); return true; });
  if (/HyimgCEF/.test(navigator.userAgent)) return /** @type {Send} */ (m => { console.log("HYIMG_MSG:" + JSON.stringify(m)); return true; });
  return null;
}
/** @param {Record<string, unknown>} m */
const send = m => { const f = B.via || appPort(); return f ? f(m) : false; };
const notify = () => B.subs.forEach(f => { try { f(); } catch (e) { console.error(e); } });
/** @param {any} b @returns {b is Browser} */
const isBrowser = b => !!b && typeof b.id === "string" && !!b.id && typeof b.name === "string" && !!b.name;

/** The app's answer. @param {any} d */
function got(d) {
  if (!d || typeof d !== "object") return;
  if (d.op === "list" && Array.isArray(d.browsers)) {
    const list = d.browsers.filter(isBrowser).map(/** @param {Browser} b */ b => ({ id: b.id, name: b.name,
      icon: typeof b.icon === "string" && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(b.icon) ? b.icon : "" }));
    B.got = list.length ? { browsers: list, default: String(d.default || ""), last: String(d.last || "") } : null;
  }
  if (d.op === "open" && B.got && typeof d.app === "string" && !d.error) B.got.last = d.app;
  if (d.op === "open" && d.error) { const toast = /** @type {any} */ (window).hyToast; if (typeof toast === "function") toast(t("The page did not open: {why}", { why: String(d.error) }), "error"); }
  notify();
}

export const hyBrowsers = {
  /** Asks the app for its browsers again (each time a studio shows the button: the default may have changed). */
  ask() { return send({ action: "browsers", op: "list" }); },
  /** @returns {Browsers | null} */
  get list() { return B.got; },
  /** The main part's browser: the one last chosen while it is still there, else the system's default. @returns {Browser | null} */
  chosen() {
    const g = B.got; if (!g) return null;
    return g.browsers.find(b => b.id === g.last) || g.browsers.find(b => b.id === g.default) || g.browsers[0] || null;
  },
  /** Opens url in that browser through the app; false when there is no app to ask. @param {string} url @param {string} id */
  open(url, id) {
    if (!B.got || !B.got.browsers.some(b => b.id === id) || !send({ action: "browsers", op: "open", url, app: id })) return false;
    B.got.last = id; notify(); return true;
  },
  /** Another way to the app (the tests), null for the app's own; what was known is forgotten. @param {Send | null} fn */
  via(fn) { B.via = fn; B.got = null; notify(); },
  /** @param {() => void} fn @returns {() => void} */
  on(fn) { B.subs.add(fn); return () => { B.subs.delete(fn); }; },
};
/** @type {any} */ (window).hyBrowsers = hyBrowsers;
/** @type {any} */ (window).hyimgBrowsers = got;

const esc = (/** @type {string} */ s) => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] || c);
const chev = () => (typeof window.hyIcon === "function" ? window.hyIcon("chevron", 12, 2.4, "oi-cv") : "");
const check = () => (typeof window.hyIcon === "function" ? window.hyIcon("check", 14, 2.4, "oi-ck") : "");

export class HyOpenIn extends HyElement {
  /** @type {() => string} */
  #target = () => "";
  #tip = "";
  /** @type {HTMLDivElement | null} */
  #menu = null;
  /** @type {(() => void) | null} */
  #off = null;
  /** @type {HTMLButtonElement | null} */
  #go = null;
  /** @type {HTMLButtonElement | null} */
  #more = null;

  connectedCallback() {
    this.upgrade("target", "tip");
    if (!this.#go) {
      const go = this.#go = document.createElement("button"); go.type = "button"; go.className = "oi-go";
      const more = this.#more = document.createElement("button"); more.type = "button"; more.className = "oi-more";
      more.setAttribute("aria-haspopup", "menu"); more.setAttribute("aria-expanded", "false"); more.setAttribute("aria-label", t("Choose a browser"));
      more.innerHTML = chev();
      go.addEventListener("click", () => this.openHere());
      more.addEventListener("click", () => (this.#menu ? this.close() : this.openMenu()));
      this.append(go, more);
    }
    this.#off = hyBrowsers.on(() => this.sync());
    this.sync(); hyBrowsers.ask();
  }

  disconnectedCallback() { if (this.#off) this.#off(); this.#off = null; this.close(); }

  /** What to open: a function, asked at the click (the page may have moved on). @returns {() => string} */
  get target() { return this.#target; }
  set target(v) { this.#target = typeof v === "function" ? v : () => String(v || ""); }
  /** The main part's tooltip while there is no browser to name (a plain browser). */
  get tip() { return this.#tip; }
  set tip(v) { this.#tip = String(v || ""); if (this.#go) this.sync(); }

  /** The words, icon and tooltip of the main part; the chevron always (without the app its menu offers the default browser alone). */
  sync() {
    const go = this.#go, more = this.#more; if (!go || !more) return;
    const b = hyBrowsers.chosen(), data = this.getAttribute("tips") === "data";
    go.innerHTML = (b && b.icon ? `<img class="oi-ic" alt="" src="${b.icon}">` : "") + `<span>${esc(b ? t("Open in {app}", { app: b.name }) : t("Open in browser"))}</span>`;
    const tip = b ? t("Open the page in {app}", { app: b.name }) : this.tip || t("Open the page in a new tab");
    if (data) { go.dataset.tip = tip; go.dataset.side = "bottom"; more.dataset.tip = t("Choose a browser"); more.dataset.side = "bottom"; }
    else { go.title = tip; more.title = t("Choose a browser"); }
    this.toggleAttribute("split", true);
    if (this.#menu) this.drawMenu();
  }

  /** The address to open, whole (a browser outside knows no page of ours to resolve a path against); "" when there is none. */
  url() { const u = this.target(); if (!u) return ""; try { return new URL(u, location.href).href; } catch { return ""; } }

  /** The main part: the chosen browser through the app, else a new tab. */
  openHere() {
    const url = this.url(); if (!url) return;
    const b = hyBrowsers.chosen();
    if (!(b && hyBrowsers.open(url, b.id))) window.open(url, "_blank", "noopener");
    this.emit("hy-open", { url, app: b ? b.id : "" });
  }

  /** @param {string} id a browser of the app's list; "" the default browser (a new tab) */
  openWith(id) {
    const url = this.url(); this.close(); if (!url) return;
    if (!(id && hyBrowsers.open(url, id))) window.open(url, "_blank", "noopener");
    this.emit("hy-open", { url, app: id });
  }

  openMenu() {
    if (this.#menu) return;
    const m = this.#menu = document.createElement("div");
    m.className = "hy-oi-menu"; m.setAttribute("role", "menu"); m.setAttribute("aria-label", t("Choose a browser"));
    m.addEventListener("click", e => { const r = /** @type {HTMLElement} */ (e.target).closest("[data-b]"); if (r instanceof HTMLElement) this.openWith(r.dataset.b || ""); });
    m.addEventListener("pointerdown", e => e.stopPropagation());
    document.body.appendChild(m); this.drawMenu();
    const r = this.getBoundingClientRect();
    m.style.top = Math.round(r.bottom + 6) + "px"; m.style.right = Math.max(8, Math.round(innerWidth - r.right)) + "px";
    if (this.#more) this.#more.setAttribute("aria-expanded", "true");
    addEventListener("keydown", this.#key, true); addEventListener("pointerdown", this.#away, true);
    const on = /** @type {HTMLElement | null} */ (m.querySelector("[aria-checked=true]") || m.querySelector("button")); if (on) on.focus({ preventScroll: true });
    hyBrowsers.ask();   // the list again: a browser installed meanwhile shows when the answer comes
  }

  close() {
    const m = this.#menu; if (!m) return; this.#menu = null; m.remove();
    if (this.#more) this.#more.setAttribute("aria-expanded", "false");
    removeEventListener("keydown", this.#key, true); removeEventListener("pointerdown", this.#away, true);
  }

  /** @private */
  drawMenu() {
    const m = this.#menu, g = hyBrowsers.list, c = hyBrowsers.chosen(); if (!m) return;
    // no list from the app: the one browser there is, the system's, which a new tab opens in; checked, as the main part's
    if (!g) { m.innerHTML = `<button type="button" role="menuitemradio" aria-checked="true" data-b="">` + check() + `<span class="oi-ic"></span>`
      + `<span class="oi-n">${esc(t("Default browser"))}</span></button>`; return; }
    m.innerHTML = g.browsers.map(b => `<button type="button" role="menuitemradio" aria-checked="${c && c.id === b.id}" data-b="${esc(b.id)}">`
      + check() + (b.icon ? `<img class="oi-ic" alt="" src="${b.icon}">` : `<span class="oi-ic"></span>`) + `<span class="oi-n">${esc(b.name)}</span>`
      + (b.id === g.default ? `<span class="oi-def">${esc(t("browser::Default").replace(/^\w+::/, ""))}</span>` : "") + `</button>`).join("");
  }

  /** Esc closes the menu and nothing else (a studio leaves on Esc); ↑ ↓ walk it, ↵ chooses; the board never sees these keys. @param {KeyboardEvent} e */
  #key = e => {
    const m = this.#menu; if (!m) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); this.close(); if (this.#more) this.#more.focus({ preventScroll: true }); return; }
    const at = document.activeElement;
    if ((e.key === "Enter" || e.key === " ") && at instanceof HTMLButtonElement && m.contains(at)) { e.preventDefault(); e.stopImmediatePropagation(); at.click(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault(); e.stopImmediatePropagation();
    const rows = [...m.querySelectorAll("button")], i = rows.indexOf(/** @type {HTMLButtonElement} */ (document.activeElement));
    const n = rows[(i + (e.key === "ArrowDown" ? 1 : rows.length - 1)) % rows.length]; if (n) n.focus({ preventScroll: true });
  };

  /** A press anywhere else closes the menu. @param {PointerEvent} e */
  #away = e => { const x = /** @type {Node} */ (e.target); if (this.#menu && !this.#menu.contains(x) && !(this.#more && this.#more.contains(x))) this.close(); };
}
define("hy-open-in", HyOpenIn);
