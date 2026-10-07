// Runs the app's browser scripts (review/ui/*.js: IIFEs that put their API on window) in node:vm with a small fake DOM and a fake
// clock, without changing or copying the files. A page is one vm context: page({ scripts: ["ui/slider.js"] }) reads each file and runs
// it in that context, as a <script> would. Timers, requestAnimationFrame and performance.now run on the fake clock (page.tick(ms)),
// so nothing waits for real time. MutationObserver records arrive on a microtask (await page.flush()), as in a browser.
//
// The DOM here is just enough for these files: elements with attributes, classList, dataset, style (setProperty), a tiny HTML parser
// for innerHTML, selectors (tag, #id, .class, [attr], [attr=v], [attr$=v], :scope, :not(), :first-child, :last-child, :nth-child(n),
// descendant and child combinators, lists),
// events with capture and bubbling, focus and blur. Layout does not exist: getBoundingClientRect and the offset / client / scroll sizes
// come from el._rect and el._box (numbers or functions), 0 when a test sets nothing.
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
export const UI = path.join(REPO, "review/ui");
export const read = rel => fs.readFileSync(path.isAbsolute(rel) ? rel : path.join(REPO, "review", rel), "utf8");
// objects made inside a vm context have that context's prototypes: compare them as plain JSON
export const plain = x => JSON.parse(JSON.stringify(x));

/* ---------------------------------------------------------------- the clock */
export function makeClock() {
  let now = 1000, seq = 0;
  const timers = new Map();
  const add = (fn, ms, every, args) => { const id = ++seq; timers.set(id, { fn, at: now + Math.max(0, +ms || 0), every, args }); return id; };
  const clock = {
    get now() { return now; },
    setTimeout: (fn, ms, ...args) => add(fn, ms, 0, args),
    setInterval: (fn, ms, ...args) => add(fn, ms, Math.max(1, +ms || 0), args),
    clear: id => { timers.delete(id); },
    raf: fn => add(t => fn(t), 16 - (now % 16 || 0) || 16, 0, []),
    pending: () => timers.size,
    // runs every timer due within ms, in time order, those they schedule included
    tick(ms = 0) {
      const end = now + ms;
      for (;;) {
        let next = null;
        for (const [id, t] of timers) if (t.at <= end && (!next || t.at < next[1].at || (t.at === next[1].at && id < next[0]))) next = [id, t];
        if (!next) break;
        const [id, t] = next; now = Math.max(now, t.at);
        if (t.every) t.at = now + t.every; else timers.delete(id);
        t.fn(...(t.args.length ? t.args : [now]));
      }
      now = end;
    },
  };
  return clock;
}

/* ---------------------------------------------------------------- selectors */
// a compound selector: tag, #id, .class, [attr op value], :scope, :not(compound)
function parseCompound(s) {
  const c = { tag: null, id: null, cls: [], attrs: [], scope: false, not: [], nth: [] };
  const re = /^(\*|[a-zA-Z][\w-]*)|#([\w-]+)|\.([\w-]+)|\[\s*([\w:-]+)\s*(?:([$^*~|]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]+)))?\s*\]|:scope|:not\(([^)]*)\)|:(first|last)-child|:nth-child\((\d+)\)/y;
  let i = 0;
  while (i < s.length) {
    re.lastIndex = i; const m = re.exec(s); if (!m || !m[0]) throw new Error("fake DOM: selector not supported: " + s);
    if (m[1]) c.tag = m[1] === "*" ? null : m[1].toUpperCase();
    else if (m[2]) c.id = m[2];
    else if (m[3]) c.cls.push(m[3]);
    else if (m[4]) c.attrs.push({ name: m[4].toLowerCase(), op: m[5] || null, value: m[6] ?? m[7] ?? m[8] ?? null });
    else if (m[0] === ":scope") c.scope = true;
    else if (m[9] != null) c.not.push(...m[9].split(",").map(x => parseCompound(x.trim())));
    else if (m[10]) c.nth.push(m[10] === "first" ? 1 : -1);
    else if (m[11]) c.nth.push(+m[11]);
    i = re.lastIndex;
  }
  return c;
}
function parseSelector(sel) {
  return splitTop(sel, ",").map(part => {
    const toks = part.trim().replace(/\s*>\s*/g, " > ").split(/\s+/).filter(Boolean), steps = [];
    let comb = " ";
    for (const t of toks) { if (t === ">") { comb = ">"; continue; } steps.push({ comb, c: parseCompound(t) }); comb = " "; }
    return steps;
  });
}
function splitTop(s, ch) {
  const out = []; let depth = 0, q = null, cur = "";
  for (const x of s) {
    if (q) { if (x === q) q = null; cur += x; continue; }
    if (x === '"' || x === "'") { q = x; cur += x; continue; }
    if (x === "(" || x === "[") depth++; else if (x === ")" || x === "]") depth--;
    if (x === ch && !depth) { out.push(cur); cur = ""; } else cur += x;
  }
  out.push(cur); return out;
}
function matchCompound(el, c, scope) {
  if (!el || el.nodeType !== 1) return false;
  if (c.scope && el !== scope) return false;
  if (c.tag && el.tagName !== c.tag) return false;
  if (c.id && el.getAttribute("id") !== c.id) return false;
  for (const k of c.cls) if (!el.classList.contains(k)) return false;
  for (const a of c.attrs) {
    const v = el.getAttribute(a.name); if (v === null) return false;
    if (a.op === "=" && v !== a.value) return false;
    if (a.op === "$=" && !v.endsWith(a.value)) return false;
    if (a.op === "^=" && !v.startsWith(a.value)) return false;
    if (a.op === "*=" && !v.includes(a.value)) return false;
    if (a.op === "~=" && !v.split(/\s+/).includes(a.value)) return false;
  }
  for (const n of c.not) if (matchCompound(el, n, scope)) return false;
  for (const k of c.nth) { const sib = el.parentNode ? el.parentNode.childNodes.filter(n => n.nodeType === 1) : [el]; if ((k < 0 ? sib[sib.length - 1] : sib[k - 1]) !== el) return false; }
  return true;
}
function matchSteps(el, steps, i, scope) {
  const { comb, c } = steps[i];
  if (!matchCompound(el, c, scope)) return false;
  if (i === 0) return true;
  if (comb === ">") return matchSteps(el.parentElement, steps, i - 1, scope);
  for (let p = el.parentElement; p; p = p.parentElement) if (matchSteps(p, steps, i - 1, scope)) return true;
  return false;
}
const matches = (el, sel, scope) => parseSelector(sel).some(steps => matchSteps(el, steps, steps.length - 1, scope));

/* ---------------------------------------------------------------- the DOM */
const VOID = new Set(["AREA", "BR", "COL", "EMBED", "HR", "IMG", "INPUT", "LINK", "META", "SOURCE", "TRACK", "WBR"]);
const decode = s => s.replace(/&(amp|lt|gt|quot|#39|apos|nbsp);/g, (m, k) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", apos: "'", nbsp: "\u00a0" })[k]);
const escText = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
const camel = s => s.replace(/-([a-z])/g, (m, x) => x.toUpperCase());
const kebab = s => s.replace(/[A-Z]/g, x => "-" + x.toLowerCase());
const REFLECT = ["id", "title", "type", "name", "min", "max", "step", "placeholder", "href", "src", "rel", "alt", "role", "lang", "for"];
const BOOL = ["hidden", "disabled", "checked"];

export function makeDOM(clock) {
  let doc = null;
  const observers = new Set();
  function notify(target, rec) {
    for (const mo of observers) for (const o of mo._targets) {
      const hit = o.node === target || (o.opts.subtree && o.node.contains(target));
      if (!hit) continue;
      if (rec.type === "attributes" && (!o.opts.attributes && !o.opts.attributeFilter || (o.opts.attributeFilter && !o.opts.attributeFilter.includes(rec.attributeName)))) continue;
      if (rec.type === "childList" && !o.opts.childList) continue;
      if (rec.type === "characterData" && !o.opts.characterData) continue;
      mo._queue.push(Object.assign({ target }, rec));
      if (!mo._scheduled) { mo._scheduled = true; queueMicrotask(() => { mo._scheduled = false; const q = mo._queue.splice(0); if (q.length && mo._on) mo._cb(q, mo); }); }
      break;
    }
  }
  class MutationObserver {
    constructor(cb) { this._cb = cb; this._targets = []; this._queue = []; this._on = true; observers.add(this); }
    observe(node, opts = {}) { if (opts.attributeFilter) opts.attributes = true; this._targets.push({ node, opts }); }
    disconnect() { this._targets = []; this._on = false; observers.delete(this); }
    takeRecords() { return this._queue.splice(0); }
  }
  const resizers = new Set();
  class ResizeObserver {
    constructor(cb) { this._cb = cb; this._els = new Set(); resizers.add(this); }
    observe(el) { this._els.add(el); }
    unobserve(el) { this._els.delete(el); }
    disconnect() { this._els.clear(); resizers.delete(this); }
  }
  // a test says «this element changed size»: its ResizeObservers run
  const resized = el => { for (const ro of resizers) if (ro._els.has(el)) ro._cb([{ target: el, contentRect: el.getBoundingClientRect() }], ro); };

  class Event {
    constructor(type, o = {}) { this.type = type; this.bubbles = !!o.bubbles; this.cancelable = o.cancelable !== false; this.defaultPrevented = false; this._stop = false; this._now = false; this.target = null; this.currentTarget = null; this.timeStamp = clock.now; }
    preventDefault() { if (this.cancelable) this.defaultPrevented = true; }
    stopPropagation() { this._stop = true; }
    stopImmediatePropagation() { this._stop = this._now = true; }
  }
  class CustomEvent extends Event { constructor(type, o = {}) { super(type, o); this.detail = o.detail ?? null; } }

  class Target {
    constructor() { this._ls = []; }
    addEventListener(type, fn, o) {
      if (!fn) return; const capture = typeof o === "boolean" ? o : !!(o && o.capture), once = !!(o && o.once);
      if (!this._ls.some(l => l.type === type && l.fn === fn && l.capture === capture)) this._ls.push({ type, fn, capture, once });
    }
    removeEventListener(type, fn, o) { const capture = typeof o === "boolean" ? o : !!(o && o.capture); this._ls = this._ls.filter(l => !(l.type === type && l.fn === fn && l.capture === capture)); }
    _fire(e, phase) {
      for (const l of this._ls.slice()) {
        if (l.type !== e.type) continue;
        if (phase === 1 && !l.capture) continue; if (phase === 3 && l.capture) continue;
        if (l.once) this.removeEventListener(l.type, l.fn, l.capture);
        e.currentTarget = this; (typeof l.fn === "function" ? l.fn : l.fn.handleEvent.bind(l.fn)).call(this, e);
        if (e._now) return;
      }
      if (phase !== 1 && typeof this["on" + e.type] === "function") this["on" + e.type].call(this, e);
    }
    dispatchEvent(e) {
      if (!e.target) e.target = this;
      const chain = []; for (let n = this._up(); n; n = n._up()) chain.push(n);
      for (let i = chain.length - 1; i >= 0 && !e._stop; i--) chain[i]._fire(e, 1);
      if (!e._stop) { this._fire(e, 1); if (!e._stop) this._fire(e, 3); }
      if (e.bubbles) for (const n of chain) { if (e._stop) break; n._fire(e, 3); }
      e.currentTarget = null;
      return !e.defaultPrevented;
    }
    _up() { return null; }
  }

  class Node extends Target {
    constructor(type) { super(); this.nodeType = type; this.parentNode = null; this.childNodes = []; this.ownerDocument = doc; }
    _up() { return this.parentNode || (this === doc ? winTarget : null); }
    get parentElement() { const p = this.parentNode; return p && p.nodeType === 1 ? p : null; }
    get firstChild() { return this.childNodes[0] || null; }
    get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
    get nextSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) + 1] || null : null; }
    get previousSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) - 1] || null : null; }
    get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === doc; }
    contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
    _adopt(n) {
      if (n.nodeType === 11) return n.childNodes.slice().map(c => this._adopt(c)).flat();
      if (n.parentNode) n.parentNode._drop(n); n.parentNode = this; return [n];
    }
    _drop(n) { const i = this.childNodes.indexOf(n); if (i >= 0) { this.childNodes.splice(i, 1); n.parentNode = null; notify(this, { type: "childList", removedNodes: [n], addedNodes: [] }); } }
    insertBefore(n, ref) {
      const list = this._adopt(n); let i = ref ? this.childNodes.indexOf(ref) : -1; if (i < 0) i = this.childNodes.length;
      this.childNodes.splice(i, 0, ...list); notify(this, { type: "childList", addedNodes: list, removedNodes: [] }); return n;
    }
    appendChild(n) { return this.insertBefore(n, null); }
    removeChild(n) { this._drop(n); return n; }
    append(...ns) { for (const n of ns) this.appendChild(typeof n === "string" ? doc.createTextNode(n) : n); }
    prepend(...ns) { const first = this.firstChild; for (const n of ns) this.insertBefore(typeof n === "string" ? doc.createTextNode(n) : n, first); }
    remove() { if (this.parentNode) this.parentNode._drop(this); }
    after(...ns) { const p = this.parentNode, nx = this.nextSibling; for (const n of ns) p.insertBefore(n, nx); }
    before(...ns) { for (const n of ns) this.parentNode.insertBefore(n, this); }
    replaceWith(n) { const p = this.parentNode; if (!p) return; p.insertBefore(n, this); p._drop(this); }
    get textContent() { return this.nodeType === 3 ? this.nodeValue : this.childNodes.map(c => c.textContent).join(""); }
    set textContent(v) {
      if (this.nodeType === 3) { this.nodeValue = String(v); notify(this, { type: "characterData" }); return; }
      for (const c of this.childNodes.slice()) this._drop(c);
      if (v != null && v !== "") this.appendChild(doc.createTextNode(String(v)));
    }
  }
  class Text extends Node {
    constructor(v) { super(3); this.nodeValue = String(v); }
    get data() { return this.nodeValue; } set data(v) { this.nodeValue = String(v); }
  }

  class ClassList {
    constructor(el) { this.el = el; }
    _get() { return (this.el.getAttribute("class") || "").split(/\s+/).filter(Boolean); }
    _set(a) { this.el.setAttribute("class", [...new Set(a)].join(" ")); }
    contains(k) { return this._get().includes(k); }
    add(...ks) { const a = this._get(); if (ks.every(k => a.includes(k))) return; this._set(a.concat(ks)); }
    remove(...ks) { const a = this._get(); if (!ks.some(k => a.includes(k))) return; this._set(a.filter(k => !ks.includes(k))); }
    toggle(k, force) { const on = force === undefined ? !this.contains(k) : !!force; if (on) this.add(k); else this.remove(k); return on; }
    replace(a, b) { if (!this.contains(a)) return false; this._set(this._get().map(k => (k === a ? b : k))); return true; }
    get length() { return this._get().length; }
    get value() { return this._get().join(" "); }
    item(i) { return this._get()[i] ?? null; }
    [Symbol.iterator]() { return this._get()[Symbol.iterator](); }
  }
  class Style {
    constructor(el) { Object.defineProperty(this, "_el", { value: el }); Object.defineProperty(this, "_p", { value: new Map() }); }
    setProperty(k, v) { this._p.set(k, String(v)); notify(this._el, { type: "attributes", attributeName: "style" }); }
    getPropertyValue(k) { if (this._p.has(k)) return this._p.get(k); const v = this[camel(k)]; return v == null ? "" : String(v); }
    removeProperty(k) { const v = this.getPropertyValue(k); this._p.delete(k); delete this[camel(k)]; return v; }
    get cssText() { return [...this._p].map(([k, v]) => `${k}: ${v}`).concat(Object.keys(this).map(k => `${kebab(k)}: ${this[k]}`)).join("; "); }
    set cssText(s) { for (const part of String(s).split(";")) { const i = part.indexOf(":"); if (i > 0) this[camel(part.slice(0, i).trim())] = part.slice(i + 1).trim(); } }
  }

  class Element extends Node {
    constructor(tag) {
      super(1); this.tagName = String(tag).toUpperCase(); this.localName = String(tag).toLowerCase(); this._attrs = new Map();
      this.classList = new ClassList(this); this.style = new Style(this); this._rect = null; this._box = {}; this._capture = new Set();
      this.dataset = new Proxy({}, {
        get: (o, k) => (typeof k === "string" ? this.getAttribute("data-" + kebab(k)) ?? undefined : undefined),
        set: (o, k, v) => { this.setAttribute("data-" + kebab(k), String(v)); return true; },
        has: (o, k) => this.hasAttribute("data-" + kebab(k)),
        deleteProperty: (o, k) => { this.removeAttribute("data-" + kebab(k)); return true; },
        ownKeys: () => [...this._attrs.keys()].filter(k => k.startsWith("data-")).map(k => camel(k.slice(5))),
        getOwnPropertyDescriptor: (o, k) => (this.hasAttribute("data-" + kebab(k)) ? { enumerable: true, configurable: true, value: this.getAttribute("data-" + kebab(k)) } : undefined),
      });
      if (this.tagName === "INPUT" || this.tagName === "TEXTAREA" || this.tagName === "SELECT" || this.tagName === "OUTPUT") this._value = null;
    }
    getAttribute(k) { k = String(k).toLowerCase(); return this._attrs.has(k) ? this._attrs.get(k) : null; }
    setAttribute(k, v) { k = String(k).toLowerCase(); const old = this.getAttribute(k); this._attrs.set(k, String(v)); if (k === "style") this.style.cssText = String(v); notify(this, { type: "attributes", attributeName: k, oldValue: old }); }
    removeAttribute(k) { k = String(k).toLowerCase(); if (!this._attrs.has(k)) return; const old = this._attrs.get(k); this._attrs.delete(k); notify(this, { type: "attributes", attributeName: k, oldValue: old }); }
    hasAttribute(k) { return this._attrs.has(String(k).toLowerCase()); }
    toggleAttribute(k, force) { const on = force === undefined ? !this.hasAttribute(k) : !!force; if (on) this.setAttribute(k, ""); else this.removeAttribute(k); return on; }
    get attributes() { return [...this._attrs].map(([name, value]) => ({ name, value })); }
    get className() { return this.getAttribute("class") || ""; } set className(v) { this.setAttribute("class", v); }
    get children() { return this.childNodes.filter(n => n.nodeType === 1); }
    get childElementCount() { return this.children.length; }
    get firstElementChild() { return this.children[0] || null; }
    get lastElementChild() { const c = this.children; return c[c.length - 1] || null; }
    get nextElementSibling() { const p = this.parentNode; if (!p) return null; const c = p.children; return c[c.indexOf(this) + 1] || null; }
    get previousElementSibling() { const p = this.parentNode; if (!p) return null; const c = p.children; return c[c.indexOf(this) - 1] || null; }
    get value() { return this._value ?? this.getAttribute("value") ?? (this.tagName === "INPUT" && this.getAttribute("type") === "range" ? "50" : ""); }
    set value(v) { this._value = String(v); }
    get isContentEditable() { return false; }
    _all() { const out = []; const walk = n => { for (const c of n.childNodes) if (c.nodeType === 1) { out.push(c); walk(c); } }; walk(this); return out; }
    querySelectorAll(sel) { return this._all().filter(el => matches(el, sel, this)); }
    querySelector(sel) { return this._all().find(el => matches(el, sel, this)) || null; }
    getElementsByTagName(t) { return this.querySelectorAll(t); }
    matches(sel) { return matches(this, sel, this); }
    closest(sel) { for (let e = this; e && e.nodeType === 1; e = e.parentNode) if (matches(e, sel, e)) return e; return null; }
    get innerHTML() { return this.childNodes.map(serialize).join(""); }
    set innerHTML(html) { for (const c of this.childNodes.slice()) this._drop(c); for (const n of parse(String(html))) this.appendChild(n); }
    get outerHTML() { return serialize(this); }
    insertAdjacentHTML(where, html) {
      const ns = parse(String(html));
      if (where === "beforeend") ns.forEach(n => this.appendChild(n)); else if (where === "afterbegin") ns.reverse().forEach(n => this.insertBefore(n, this.firstChild));
      else if (where === "beforebegin") ns.forEach(n => this.parentNode.insertBefore(n, this)); else { let ref = this.nextSibling; ns.forEach(n => this.parentNode.insertBefore(n, ref)); }
    }
    _size(k) { const v = this._box[k]; return typeof v === "function" ? v(this) : v || 0; }
    getBoundingClientRect() {
      const r = typeof this._rect === "function" ? this._rect(this) : this._rect || {};
      const left = r.left ?? r.x ?? 0, top = r.top ?? r.y ?? 0, width = r.width ?? this._size("offsetWidth"), height = r.height ?? this._size("offsetHeight");
      return { left, top, x: left, y: top, width, height, right: left + width, bottom: top + height };
    }
    getClientRects() { return [this.getBoundingClientRect()]; }
    get offsetWidth() { return this._size("offsetWidth"); } get offsetHeight() { return this._size("offsetHeight"); }
    get offsetLeft() { return this._size("offsetLeft"); } get offsetTop() { return this._size("offsetTop"); }
    get clientWidth() { return this._box.clientWidth !== undefined ? this._size("clientWidth") : this._size("offsetWidth"); }
    get clientHeight() { return this._box.clientHeight !== undefined ? this._size("clientHeight") : this._size("offsetHeight"); }
    get scrollWidth() { return this._box.scrollWidth !== undefined ? this._size("scrollWidth") : this.clientWidth; }
    get scrollHeight() { return this._box.scrollHeight !== undefined ? this._size("scrollHeight") : this.clientHeight; }
    setPointerCapture(id) { this._capture.add(id); }
    releasePointerCapture(id) { this._capture.delete(id); }
    hasPointerCapture(id) { return this._capture.has(id); }
    focus() { const was = doc.activeElement; if (was === this) return; doc.activeElement = this; if (was && was !== doc.body) was.dispatchEvent(new Event("blur")); this.dispatchEvent(new Event("focus")); }
    blur() { if (doc.activeElement !== this) return; doc.activeElement = doc.body; this.dispatchEvent(new Event("blur")); }
    select() {}
    click() { this.dispatchEvent(Object.assign(new Event("click", { bubbles: true }), { button: 0 })); }
    scrollIntoView() { this._scrolledIntoView = (this._scrolledIntoView || 0) + 1; }
    attachShadow() { const r = new Element("#shadow-root"); r.host = this; this.shadowRoot = r; return r; }
    getContext() { return this._ctx || (this._ctx = canvasContext(this)); }
    canPlayType(type) { return doc._canPlay ? doc._canPlay(type) || "" : ""; }
    toDataURL() { return "data:image/png;base64,FAKE"; }
  }
  for (const k of REFLECT) Object.defineProperty(Element.prototype, k, { get() { return this.getAttribute(k) ?? ""; }, set(v) { this.setAttribute(k, v); }, configurable: true });
  for (const k of BOOL) Object.defineProperty(Element.prototype, k, { get() { return this.hasAttribute(k); }, set(v) { this.toggleAttribute(k, !!v); }, configurable: true });

  // a 2D context that only records what it is asked (paper.js draws its grain with it)
  function canvasContext(cv) {
    const calls = [];
    return new Proxy({ canvas: cv, calls, createImageData: (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }) }, {
      get(o, k) { if (k in o) return o[k]; return (...a) => { calls.push([k, ...a]); }; },
      set(o, k, v) { o[k] = v; return true; },
    });
  }

  function serialize(n) {
    if (n.nodeType === 3) return escText(n.nodeValue);
    const attrs = [...n._attrs].map(([k, v]) => (v === "" ? ` ${k}` : ` ${k}="${escAttr(v)}"`)).join("");
    return `<${n.localName}${attrs}>` + (VOID.has(n.tagName) ? "" : n.childNodes.map(serialize).join("") + `</${n.localName}>`);
  }
  function parse(html) {
    const root = new Element("#fragment"), stack = [root];
    const re = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+|<)/g;
    let m;
    while ((m = re.exec(html))) {
      const top = stack[stack.length - 1];
      if (m[1]) { const t = m[1].toUpperCase(); for (let i = stack.length - 1; i > 0; i--) if (stack[i].tagName === t) { stack.length = i; break; } }
      else if (m[2]) {
        const el = new Element(m[2]);
        for (const a of m[3].matchAll(/([^\s=>\/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) el._attrs.set(a[1].toLowerCase(), decode(a[2] ?? a[3] ?? a[4] ?? ""));
        top.appendChild(el);
        if (!m[4] && !VOID.has(el.tagName)) stack.push(el);
      } else if (m[5]) top.appendChild(new Text(decode(m[5])));
    }
    const out = root.childNodes.slice(); out.forEach(n => { root.childNodes.length = 0; n.parentNode = null; }); return out;
  }

  class Document extends Node {
    constructor() { super(9); }
  }
  const winTarget = new Target();
  doc = new Document();
  doc.ownerDocument = null;
  const html = new Element("html"), head = new Element("head"), body = new Element("body");
  doc.appendChild(html); html.appendChild(head); html.appendChild(body);
  Object.assign(doc, {
    documentElement: html, head, body, readyState: "complete", activeElement: body, currentScript: null, hidden: false, visibilityState: "visible", title: "",
    createElement: t => new Element(t),
    createElementNS: (ns, t) => new Element(t),
    createTextNode: v => new Text(v),
    createDocumentFragment: () => { const f = new Element("#fragment"); f.nodeType = 11; return f; },
    querySelector: s => (matches(html, s, html) ? html : html.querySelector(s)),
    querySelectorAll: s => (matches(html, s, html) ? [html] : []).concat(html.querySelectorAll(s)),
    getElementById: id => html.querySelector("#" + id),
    elementFromPoint: () => null,
    get scrollingElement() { return html; },
    // only what i18n.js asks: the text nodes under root, in order, through its filter
    createTreeWalker(root, what, filter) {
      const list = []; const walk = n => { for (const c of n.childNodes) { if (c.nodeType === 3) { const r = filter && filter.acceptNode ? filter.acceptNode(c) : 1; if (r === 1) list.push(c); } else if (c.nodeType === 1) walk(c); } };
      walk(root); let i = -1;
      return { get currentNode() { return list[i]; }, nextNode: () => (++i < list.length ? list[i] : null) };
    },
  });
  return { doc, winTarget, Element, Text, Event, CustomEvent, MutationObserver, ResizeObserver, resized, parse };
}

/* ---------------------------------------------------------------- the page */
// opts: scripts (paths under review/ or absolute), storage {k: v}, globals (extra window properties), fetch (a stub), width, height,
// canPlay (type -> "" | "maybe" | "probably": what the engine's <video>.canPlayType answers)
export function page(opts = {}) {
  const clock = makeClock();
  const win = {};
  const dom = makeDOM(clock), winTarget = dom.winTarget;
  const store = new Map(Object.entries(opts.storage || {}));
  const localStorage = {
    getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: k => store.delete(k),
    clear: () => store.clear(), key: i => [...store.keys()][i] ?? null, get length() { return store.size; },
  };
  const calls = { fetch: [], console: [] };
  const fetchStub = opts.fetch || (async () => { throw new Error("no network in unit tests"); });
  class Image { constructor(w, h) { this.width = w; this.height = h; this.style = {}; } decode() { return Promise.resolve(); } }
  Object.assign(win, {
    document: dom.doc, localStorage, sessionStorage: localStorage,
    navigator: { userAgent: "node-unit", language: "en-US", platform: "MacIntel" },
    location: { href: "http://localhost/review/canvas.html", origin: "http://localhost", pathname: "/review/canvas.html", search: "", reload() { calls.reload = (calls.reload || 0) + 1; } },
    innerWidth: opts.width || 1280, innerHeight: opts.height || 800, devicePixelRatio: 2, scrollX: 0, scrollY: 0,
    setTimeout: clock.setTimeout, clearTimeout: clock.clear, setInterval: clock.setInterval, clearInterval: clock.clear,
    requestAnimationFrame: clock.raf, cancelAnimationFrame: clock.clear,
    performance: { now: () => clock.now },
    queueMicrotask, URL, URLSearchParams, TextEncoder, TextDecoder, structuredClone, Blob: globalThis.Blob, AbortController,
    console: { log: (...a) => calls.console.push(["log", ...a]), warn: (...a) => calls.console.push(["warn", ...a]), error: (...a) => calls.console.push(["error", ...a]), info() {}, debug() {} },
    fetch: (...a) => { calls.fetch.push(a); return fetchStub(...a); },
    Event: dom.Event, CustomEvent: dom.CustomEvent, KeyboardEvent: dom.Event, PointerEvent: dom.Event, MouseEvent: dom.Event, WheelEvent: dom.Event, FocusEvent: dom.Event,
    MutationObserver: dom.MutationObserver, ResizeObserver: dom.ResizeObserver, Image,
    NodeFilter: { SHOW_TEXT: 4, SHOW_ELEMENT: 1, FILTER_ACCEPT: 1, FILTER_REJECT: 2, FILTER_SKIP: 3 },
    CSS: { escape: s => String(s).replace(/["\\]/g, "\\$&"), supports: () => true },
    // what a test put in el._computed, else the inline style, else the initial value of the few properties these files read
    getComputedStyle: el => new Proxy({}, { get: (o, k) => (k === "getPropertyValue" ? p => (el._computed && el._computed[p]) || el.style.getPropertyValue(p) : (el._computed && el._computed[k]) ?? (el.style[k] || undefined) ?? ({ opacity: "1", visibility: "visible", pointerEvents: "auto", display: "block" })[k] ?? "") }),
    matchMedia: q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
    addEventListener: (...a) => winTarget.addEventListener(...a),
    removeEventListener: (...a) => winTarget.removeEventListener(...a),
    dispatchEvent: e => winTarget.dispatchEvent(e),
  }, opts.globals || {});
  win.window = win.self = win.top = win.parent = win.globalThis = win;
  const ctx = vm.createContext(win);
  const P = {
    window: win, ctx, clock, dom, document: dom.doc, store, calls,
    run(code, filename = "inline.js") { return vm.runInContext(code, ctx, { filename }); },
    load(...files) { for (const f of files) vm.runInContext(read(f), ctx, { filename: path.isAbsolute(f) ? f : path.join(REPO, "review", f) }); return P; },
    tick: ms => clock.tick(ms),
    // the microtasks (MutationObserver records, promise callbacks) and the timers due now
    async flush(times = 3) { for (let i = 0; i < times; i++) { await new Promise(r => setImmediate(r)); clock.tick(0); } },
    el(tag, attrs = {}, parent) { const e = dom.doc.createElement(tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.appendChild(e); return e; },
    html(markup, parent = dom.doc.body) { const ns = dom.parse(markup); ns.forEach(n => parent.appendChild(n)); return ns.find(n => n.nodeType === 1); },
    // an event as the browser makes it: its props (clientX, key, button, pointerId, ...) on it
    fire(target, type, props = {}, o = { bubbles: true }) { const e = Object.assign(new dom.Event(type, o), { button: 0, pointerId: 1, shiftKey: false, altKey: false, metaKey: false, ctrlKey: false }, props); target.dispatchEvent(e); return e; },
  };
  if (opts.canPlay) dom.doc._canPlay = opts.canPlay;
  if (opts.scripts) P.load(...opts.scripts);
  return P;
}
