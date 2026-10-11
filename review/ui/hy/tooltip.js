// @ts-check
// <hy-tooltip>: the one tooltip of the app (owner 2026-10-11 on round 20, question 11, version A «Одна своя подсказка»: «идеально!!! и
// возможность их отключить в Tips and shortcuts и в настройках тоже»). The glass of the menus, the name, a quiet line when there is one, the
// keys as caps (Figma, Linear): «Library ⌘ M», «Undo  Moved 3 pictures  ⌘ Z». 400 ms under the pointer before the first, at once for the
// next one while a tooltip is up or has just gone. The look is ui/hy/tooltip.css.
//
// One listener on the document does every element of the page: a button names itself the way it always did and needs nothing else.
//   title="Library · ⌘M"            the board, the library, Home, the 3D and Dev Studios: the words, and after « · » the keys (caps);
//                                   «⌘↵ or Esc» reads ⌘↵ / Esc. While the pointer is on it the title rests in data-hy-title, so the
//                                   system's own tooltip never shows; it comes back when the pointer leaves, and the element keeps an
//                                   aria-label (or aria-description) with the same words for VoiceOver
//   data-tip="Brush" data-key="B"   Image Studio's way (data-key: caps apart by a space, «H Space»); data-tip-sub a quiet line;
//   data-side="left|right|top|bottom" where it stands (else under the element, over it when there is no room); data-first="mask" at once
//                                   and tinted the first time ever
//   el.hyTip = () => ({ t, sub, keys, things })   words that change (the dock's Undo names its step); things { urls, more }: pictures
//                                   as small tiles after the quiet line, three and «+N» (the step's, round 21)
//   data-notip                      none here (a big surface whose title is only for the screen reader)
// For a page's script: hyTooltip.show(el, spec?, { live }) shows one now (after ⌘Z the step's name over Undo), hide(el?), refresh(el)
// when the words of the one shown changed, on() the setting. A page that has menus says when they block it: window.hyTooltipConfig =
// { block() { return menuOpen(); }, left() { return INSET; } } (left: where the free part of the page begins).
//
// Settings › Interface › Tooltips and the «?» panel's switch: cv.tooltips "0" turns them off (Home, a file page, mirrors its setting on
// <html data-tooltips>). A classic script on Home, a module elsewhere (ui/hy/index.js imports it): one file, no import, no export.
(() => {
  const W = /** @type {any} */ (typeof window === "undefined" ? {} : window);
  if (W.hyTooltip || typeof document === "undefined" || typeof W.addEventListener !== "function") return;   // once a page; nothing without a DOM (node's tests)
  const DELAY = 400, NEAR = 400;   // ms: the rest before the first, and how long after one went the next comes at once
  const MOD = "⌘⇧⌥⌃";
  const KEYWORD = /^(Esc|Space|Tab|Enter|Delete|Пробел|Home|End|PageUp|PageDown|F\d{1,2})$/;
  /** @param {string} s */
  const isCombo = s => {
    const k = s.replace(new RegExp(`^[${MOD}]+`), "");
    if (!k) return s.length > 0 && s.length <= 4;   // ⌘ or ⇧⌘ alone, held
    return KEYWORD.test(k) || /^([A-Z0-9↵⌫⇥←↑→↓.,\\[\]/+\-−=`'!@*]|[←↑→↓]{2,4})$/.test(k);
  };
  /** One combination as caps: «⇧⌘Z» -> ⇧ ⌘ Z, «←↑→↓» -> each arrow. @param {string} s */
  const capsOf = s => {
    const out = []; let i = 0;
    while (i < s.length && MOD.includes(s[i])) out.push(s[i++]);
    const rest = s.slice(i);
    if (/^[←↑→↓]{2,}$/.test(rest)) out.push(...rest); else if (rest) out.push(rest);
    return out;
  };
  /**
   * «Words · keys» into its parts; a tail that is not keys stays in the words.
   * @param {string} text
   * @returns {{ t: string, keys: string[][], after: string }}
   */
  function parse(text) {
    const s = String(text || "").trim(), at = s.lastIndexOf(" · ");
    if (at < 0) return { t: s, keys: [], after: "" };
    const tail = s.slice(at + 3).split(/\s+/);
    if (!isCombo(tail[0])) return { t: s, keys: [], after: "" };
    const keys = []; let i = 0;
    for (; i < tail.length; i++) {
      const w = tail[i];
      if (/^(or|или|\/)$/.test(w)) { if (!keys.length || !tail[i + 1] || !isCombo(tail[i + 1])) break; }   // «⌘↵ or Esc»: one or the other
      else if (isCombo(w)) keys.push(capsOf(w));
      else break;
    }
    return { t: s.slice(0, at), keys, after: tail.slice(i).join(" ") };
  }

  /** @typedef {{ t?: string, sub?: string, keys?: string | string[] | string[][], after?: string, things?: { urls: string[], more?: number } | null }} Spec */
  /** @param {any} el @returns {Spec | null} */
  function specOf(el) {
    if (!el) return null;
    if (el.hyTip) { try { const v = typeof el.hyTip === "function" ? el.hyTip() : el.hyTip; if (v) return v; } catch (e) { console.error("tooltip", e); } }
    const d = el.dataset || {};
    if (d.tip != null && d.tip !== "") return { t: d.tip, sub: d.tipSub || "", keys: d.key ? d.key.split(" ").filter(Boolean).map(capsOf) : undefined };
    const words = d.hyTitle || (el.getAttribute && el.getAttribute("title")) || "";
    return words ? parse(words) : null;
  }
  /** @param {Spec} sp @returns {string[][]} */
  const keysOf = sp => {
    const k = sp.keys;
    if (!k) return [];
    if (typeof k === "string") return k.split(/\s+\/\s+|\s+or\s+/).map(capsOf);
    return k.map(g => (Array.isArray(g) ? g : capsOf(g)));
  };

  /** @returns {boolean} the setting: on unless turned off */
  function on() {
    const d = document.documentElement.dataset.tooltips;
    if (d) return d !== "0";
    try { return localStorage.getItem("cv.tooltips") !== "0"; } catch { return true; }
  }
  const cfg = () => W.hyTooltipConfig || {};
  const blocked = () => { try { return !!(cfg().block && cfg().block()); } catch { return false; } };

  /** @type {HTMLElement | null} */ let el = null;
  /** @type {Element | null} */ let forEl = null;   // the element it names now (or is about to)
  /** @type {Element | null} */ let pressed = null;   // pressed: no tooltip for it until the pointer has left it
  let timer = 0, gone = 0, held = false;
  /** @type {{ x: number, y: number }} */ let ptr = { x: 0, y: 0 };

  function make() {
    if (el && el.isConnected) return el;
    el = document.createElement("hy-tooltip"); el.id = "hytip"; el.setAttribute("aria-hidden", "true");
    (document.body || document.documentElement).append(el);
    return el;
  }
  /** @param {Element} a @param {string} t */
  const cap = (a, t) => { const k = document.createElement("hy-kbd"); k.setAttribute("size", "m"); k.textContent = t; a.append(k); };
  /** @param {HTMLElement} box @param {Spec} sp */
  function fill(box, sp) {
    box.textContent = "";
    const t = String(sp.t || ""), keys = keysOf(sp);
    const w = document.createElement("span"); w.className = "tt-t"; w.textContent = t; box.append(w);
    if (sp.sub) { const s = document.createElement("span"); s.className = "tt-s"; s.textContent = sp.sub; box.append(s); }
    const urls = (sp.things && sp.things.urls || []).filter(Boolean), more = (sp.things && sp.things.more) || 0;
    if (urls.length) {   // the step's pictures (round 21): tiles overlapped, then «+N»
      const th = document.createElement("span"); th.className = "tt-th";
      urls.slice(0, 3).forEach(u => { const b = document.createElement("b"); b.style.backgroundImage = `url("${String(u).replace(/["\\]/g, "")}")`; th.append(b); });
      if (more > 0) { const m = document.createElement("em"); m.textContent = "+" + more; th.append(m); }
      box.append(th);
    }
    if (keys.length) {
      const k = document.createElement("span"); k.className = "tt-k";
      keys.forEach((g, i) => { if (i) { const o = document.createElement("span"); o.className = "tt-or"; o.textContent = "/"; k.append(o); } g.forEach(c => cap(k, c)); });
      box.append(k);
    }
    if (sp.after) { const a = document.createElement("span"); a.className = "tt-s"; a.textContent = sp.after; box.append(a); }
    box.toggleAttribute("keys", keys.length > 0 && !sp.after);
    box.toggleAttribute("long", (t + (sp.sub || "")).length > 64);
  }
  /** @param {Element} target @param {HTMLElement} box @param {boolean} fresh */
  function place(target, box, fresh) {
    const r = target.getBoundingClientRect(), tw = box.offsetWidth, th = box.offsetHeight, vw = innerWidth, vh = innerHeight, gap = 10;
    const side = /** @type {HTMLElement} */ (target).dataset?.side || "";
    let x, y, ox = 0, oy = 0;
    if (r.width > 260 || r.height > 140) { x = ptr.x - tw / 2; y = ptr.y + 22; oy = -4; }   // a big thing: at the pointer, not at its middle
    else if (side === "right") { x = r.right + gap; y = r.top + r.height / 2 - th / 2; ox = -4; }
    else if (side === "left") { x = r.left - gap - tw; y = r.top + r.height / 2 - th / 2; ox = 4; }
    else if (side === "top" || (side !== "bottom" && r.bottom + gap + th > vh - 8)) { x = r.left + r.width / 2 - tw / 2; y = r.top - gap - th; oy = 4; }
    else { x = r.left + r.width / 2 - tw / 2; y = r.bottom + gap; oy = -4; }
    let left = 8; try { left = Math.max(8, (+(cfg().left ? cfg().left() : 0) || 0) + 8); } catch { /* the page's own bound failed: the window's */ }
    x = Math.max(left, Math.min(x, vw - tw - 8)); y = Math.max(8, Math.min(y, vh - th - 8));
    if (fresh) { box.style.transition = "none"; box.style.transform = `translate(${Math.round(x + ox)}px, ${Math.round(y + oy)}px)`; box.offsetWidth; box.style.transition = ""; }
    box.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  }

  /** @param {Element} target @param {Spec | null} [spec] @param {{ live?: boolean, first?: boolean }} [o] */
  function show(target, spec, o = {}) {
    clearTimeout(timer); timer = 0;
    if (!target || !target.isConnected || !target.getClientRects().length) return;
    const sp = spec || specOf(target); if (!sp || !(sp.t || sp.sub)) { hide(); return; }
    const box = make(), fresh = !box.hasAttribute("shown");
    fill(box, sp); box.toggleAttribute("first", !!o.first);
    if (o.live) { box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); box.removeAttribute("aria-hidden"); }
    else { box.removeAttribute("role"); box.removeAttribute("aria-live"); box.setAttribute("aria-hidden", "true"); }
    held = !!spec; if (forEl !== target) unstash(forEl); forEl = target;
    place(target, box, fresh); box.setAttribute("shown", "");
  }
  /** @param {Element | null} [target] only when it is the one named now */
  function hide(target) {
    if (target && target !== forEl) return;
    clearTimeout(timer); timer = 0;
    if (el && el.hasAttribute("shown")) { gone = performance.now(); el.removeAttribute("shown"); }
    unstash(forEl); forEl = null; held = false;
  }
  /** the words of the element named now changed: the tooltip follows (a disabled mode that became enabled) @param {Element} target */
  function refresh(target) { if (target === forEl && el && el.hasAttribute("shown") && !held) show(target); }

  // the title rests while the pointer is on the element, so the system's tooltip never shows; VoiceOver keeps its words
  /** @param {any} t */
  function stash(t) {
    const w = t.getAttribute && t.getAttribute("title"); if (!w) return;
    t.dataset.hyTitle = w; t.removeAttribute("title");
    if (!t.hasAttribute("aria-label") && !(t.textContent || "").trim()) t.setAttribute("aria-label", parse(w).t);
    else if (!t.hasAttribute("aria-label") && !t.hasAttribute("aria-description")) t.setAttribute("aria-description", w);
  }
  /** @param {any} t */
  function unstash(t) {
    if (!t || !t.dataset || t.dataset.hyTitle == null) return;
    if (!t.hasAttribute("title")) t.setAttribute("title", t.dataset.hyTitle);
    delete t.dataset.hyTitle;
  }
  /** the element under the pointer that has words for a tooltip @param {EventTarget | null} n @returns {Element | null} */
  function targetOf(n) {
    let t = /** @type {any} */ (n);
    while (t && t.nodeType === 1 && !(t.hyTip || t.hasAttribute("data-tip") || t.hasAttribute("title") || t.hasAttribute("data-hy-title") || t.hasAttribute("data-notip")))
      t = t.parentElement;
    if (!t || t.nodeType !== 1 || t.hasAttribute("data-notip") || /^(IFRAME|HTML|BODY|OPTION)$/.test(t.tagName) || t.closest("hy-tooltip")) return null;
    return t.hyTip || t.getAttribute("data-tip") || t.getAttribute("title") || t.dataset.hyTitle ? t : null;
  }

  document.addEventListener("pointerover", e => {
    ptr = { x: e.clientX, y: e.clientY };
    if (e.pointerType === "touch") return;
    const t = targetOf(e.target);
    // the same element: nothing new, unless it shows a step said after ⌘Z and the pointer came back to it (its own words return)
    if (t === forEl && (!held || t === pressed)) return;
    if (pressed && t !== pressed) pressed = null;
    if (!t || e.buttons || t === pressed || !on() || blocked()) { if (!held) hide(); return; }   // a step said after ⌘Z stays its 2 s
    if (forEl) unstash(forEl);
    stash(t); forEl = t; held = false;
    let first = false;
    const f = /** @type {HTMLElement} */ (t).dataset.first;
    if (f) { try { first = !localStorage.getItem("hy-ed-first-" + f); localStorage.setItem("hy-ed-first-" + f, "1"); } catch { first = false; } }
    const now = (el && el.hasAttribute("shown")) || performance.now() - gone < NEAR;
    clearTimeout(timer);
    timer = setTimeout(() => { timer = 0; if (forEl === t && t.matches(":hover")) show(t, null, { first }); }, now || first ? 0 : DELAY);
  }, true);
  document.addEventListener("pointerout", e => {
    if (!forEl || held) return;
    const to = /** @type {Node | null} */ (e.relatedTarget);
    if (!to || !forEl.contains(to)) { if (!to || !targetOf(to)) hide(); }
  }, true);
  document.addEventListener("pointermove", e => { ptr = { x: e.clientX, y: e.clientY }; }, { capture: true, passive: true });
  // a press, a key, a scroll: the tooltip goes, and the pressed thing shows none until the pointer has left it
  document.addEventListener("pointerdown", e => { pressed = targetOf(e.target); hide(); }, true);
  addEventListener("keydown", e => { if (!/^(Meta|Shift|Alt|Control|CapsLock)$/.test(e.key)) hide(); }, true);
  addEventListener("wheel", () => hide(), { capture: true, passive: true });
  addEventListener("blur", () => hide());

  W.hyTooltip = { show, hide, refresh, on, parse, specOf, DELAY, get el() { return el; }, get target() { return forEl; } };
  // the element: a name for the tag, so customElements knows it (it has no behaviour of its own)
  if (window.customElements && !customElements.get("hy-tooltip")) customElements.define("hy-tooltip", class extends HTMLElement {});
})();
