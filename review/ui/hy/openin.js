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
import { define, t } from "./base.js";
import { HySplit, esc } from "./split.js";

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

const chev = () => (typeof window.hyIcon === "function" ? window.hyIcon("chevron", 12, 2.4, "oi-cv") : "");
const check = () => (typeof window.hyIcon === "function" ? window.hyIcon("check", 14, 2.4, "oi-ck") : "");

// <hy-split> with the browsers as its menu (ui/hy/split.js: the split, the menu, its keys, a press elsewhere; owner 2026-10-10: one primitive)
export class HyOpenIn extends HySplit {
  /** @type {() => string} */
  #target = () => "";
  #tip = "";
  /** @type {(() => void) | null} */
  #off = null;

  connectedCallback() {
    this.upgrade("target", "tip");
    super.connectedCallback();
    if (this._more) { this._more.innerHTML = chev(); this._more.setAttribute("aria-label", t("Choose a browser")); }
    if (!this.#off) this.#off = hyBrowsers.on(() => this.sync());
    this.sync(); hyBrowsers.ask();
  }

  disconnectedCallback() { if (this.#off) this.#off(); this.#off = null; super.disconnectedCallback(); }

  menuLabel() { return t("Choose a browser"); }

  /** What to open: a function, asked at the click (the page may have moved on). @returns {() => string} */
  get target() { return this.#target; }
  set target(v) { this.#target = typeof v === "function" ? v : () => String(v || ""); }
  /** The main part's tooltip while there is no browser to name (a plain browser). */
  get tip() { return this.#tip; }
  set tip(v) { this.#tip = String(v || ""); if (this._go) this.sync(); }

  /** The words, icon and tooltip of the main part; the chevron always (without the app its menu offers the default browser alone). */
  sync() {
    const go = this._go, more = this._more; if (!go || !more) return;
    const b = hyBrowsers.chosen(), data = this.getAttribute("tips") === "data";
    go.innerHTML = (b && b.icon ? `<img class="oi-ic" alt="" src="${b.icon}">` : "") + `<span>${esc(b ? t("Open in {app}", { app: b.name }) : t("Open in browser"))}</span>`;
    const tip = b ? t("Open the page in {app}", { app: b.name }) : this.tip || t("Open the page in a new tab");
    if (data) { go.dataset.tip = tip; go.dataset.side = "bottom"; more.dataset.tip = t("Choose a browser"); more.dataset.side = "bottom"; }
    else { go.title = tip; more.title = t("Choose a browser"); }
    this.toggleAttribute("split", true);
    if (this._menu) this.drawMenu();
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

  /** @param {HTMLElement} row */
  choose(row) { this.openWith(row.dataset.b || ""); }

  opened() { hyBrowsers.ask(); }   // the list again: a browser installed meanwhile shows when the answer comes

  drawMenu() {
    const m = this._menu, g = hyBrowsers.list, c = hyBrowsers.chosen(); if (!m) return;
    // no list from the app: the one browser there is, the system's, which a new tab opens in; checked, as the main part's
    if (!g) { m.innerHTML = `<button type="button" role="menuitemradio" aria-checked="true" data-b="">` + check() + `<span class="oi-ic"></span>`
      + `<span class="oi-n">${esc(t("Default browser"))}</span></button>`; return; }
    m.innerHTML = g.browsers.map(b => `<button type="button" role="menuitemradio" aria-checked="${c && c.id === b.id}" data-b="${esc(b.id)}">`
      + check() + (b.icon ? `<img class="oi-ic" alt="" src="${b.icon}">` : `<span class="oi-ic"></span>`) + `<span class="oi-n">${esc(b.name)}</span>`
      + (b.id === g.default ? `<span class="oi-def">${esc(t("browser::Default").replace(/^\w+::/, ""))}</span>` : "") + `</button>`).join("");
  }
}
define("hy-open-in", HyOpenIn);
