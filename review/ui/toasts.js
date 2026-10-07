// One kind of notification for every Hyimg page (owner 2026-10-04: the canvas showed its notes at the top and the library at the bottom,
// in two looks). A stack at the top centre of the window, as notifications on the iPhone's lock screen (owner 2026-10-05: «one after
// another, the top one does not leave at once»): the newest stands in front, the older ones tuck in behind it a little lower and smaller,
// the pointer on the stack fans it out into a list and holds every timer; each leaves after its own time, the oldest first.
// Glass with blur like the panels; the colour says what it is: error red, news or a note blue, success green; light and dark themes.
// hyToast(text, kind?, {sticky}?) — kind "error" | "info" | "success"; without it the words decide. A sticky one (something to act on,
// owner 2026-10-04: «key notes that matter in the moment can stay, with a × on the right to close») stays until its × is pressed. The canvas inside the library page sends its
// notes up here, so one stack shows everything. They stand in the window's middle, an open library or not (owner 2026-10-04); --toast-x on <html> can move them, 50% by default.
// They stand under the top row in every mode, on its --hy-row-under line (ui/look.css, 58 px): a note never covers the crumb, a title plate or
// «To the original» (owner 2026-10-07, the 3D studio's «scene saved» over the scene's title); --toast-top on <html> can move them.
(() => {
  if (window.hyToast) return;
  const css = `
#hyToasts { position: fixed; top: var(--toast-top, var(--hy-row-under, 58px)); left: var(--toast-x, 50%); transform: translateX(-50%); z-index: 1000; pointer-events: none;
  width: var(--ht-w, 320px); max-width: calc(100vw - 32px); height: var(--ht-h, 0px); transition: top .3s cubic-bezier(.32,.72,0,1); }
#hyToasts:not(:empty) { pointer-events: auto; }
#hyToasts .ht { --k: var(--ht-info); position: absolute; transform-origin: 50% 0; left: 0; right: 0; top: 0; box-sizing: border-box; display: flex; align-items: center; gap: 10px; padding: 9px 16px 9px 14px; border-radius: var(--ht-r, 999px);
  font: 500 13px/1.4 var(--sans, -apple-system, system-ui, sans-serif); color: var(--k); cursor: default;   /* the words in the kind's colour, as its dot (owner 2026-10-06) */
  /* light (owner 2026-10-06: «the outline is too bright, it takes the attention; the colour more muted and see-through»): the kind is
     the dot, the plate barely tinted, the edge the panels' hairline */
  /* 86% of the panel under the blur (was 74%): over the board's frame WebKit does not blur what lies in another document, and a bar's
     icon under the note read as drawn over its words (owner 2026-10-06, «Raw Editor» with the colour disc over its first letters) */
  background: color-mix(in srgb, var(--k) 6%, color-mix(in srgb, var(--panel, #18181b) 86%, transparent));
  border: 1px solid color-mix(in srgb, var(--k) 10%, var(--line, rgba(255,255,255,.1)));
  -webkit-backdrop-filter: blur(20px) saturate(1.5); backdrop-filter: blur(20px) saturate(1.5); box-shadow: 0 10px 32px rgba(0,0,0,.28);
  opacity: 0; transform: translateY(-14px) scale(.96); transition: opacity .32s cubic-bezier(.32,.72,0,1), transform .42s cubic-bezier(.32,.72,0,1); }
#hyToasts .ht > * { transition: opacity .25s ease; }
#hyToasts .ht.behind:not(.fan) > * { opacity: 0; }   /* a card tucked behind shows only its edge, its words come back when the stack fans out */
#hyToasts .ht i { flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--k); box-shadow: 0 0 0 3px color-mix(in srgb, var(--k) 14%, transparent); }
:root[data-shape="pro"] #hyToasts .ht { --ht-r: 14px; }   /* rounded like the rest: a capsule, the pro shape's plate corner */
#hyToasts .ht.error { --k: var(--ht-error); } #hyToasts .ht.success { --k: var(--ht-success); }
#hyToasts .ht .x { flex: none; width: 22px; height: 22px; margin: -3px -6px -3px 2px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: inherit; opacity: .6;
  display: grid; place-items: center; cursor: pointer; font: inherit; } #hyToasts .ht .x:hover { opacity: 1; background: color-mix(in srgb, currentColor 12%, transparent); }
#hyToasts .ht.act > span { flex: 1; min-width: 0; }
#hyToasts .ht .ab { flex: none; height: 24px; margin: -3px -4px -3px 0; padding: 0 8px; border: 0; border-radius: 7px; background: transparent; color: var(--k); font: 600 12.5px var(--sans, -apple-system, system-ui, sans-serif);
  cursor: pointer; white-space: nowrap; transition: background .15s cubic-bezier(.32,.72,0,1); } #hyToasts .ht .ab:hover { background: color-mix(in srgb, var(--k) 16%, transparent); }
:root { --ht-info: #0a84ff; --ht-success: #30d158; --ht-error: #ff453a; }
:root[data-theme="light"] { --ht-info: #007aff; --ht-success: #248a3d; --ht-error: #d70015; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { --ht-info: #007aff; --ht-success: #248a3d; --ht-error: #d70015; } }
@media (prefers-reduced-motion: reduce) { #hyToasts .ht { transition: opacity .15s; } }`;
  // the kind by the words when a caller gives none, in either language (owner 2026-10-06: two languages); callers pass it mostly
  const ERR = /не получилось|не удалось|не сохранил|не сохранен|не загрузил|не записан|не ответил|не удалить|сбросила|ошибк|нельзя|couldn't|could not|can't|cannot|failed|not saved|didn't save|wasn't saved|not loaded|didn't load|not written|didn't answer|not responding|no answer|connection (was )?(reset|dropped)|error|not allowed|⚠/i;
  const OK = /^(версия сохранена|картинка скопирована|сохранено|готово|version saved|image copied|saved|done)|снова на холсте|back on the canvas/i;
  // the words in the app's language (ui/i18n.js; its Russian in ui/lang-common.js, owner 2026-10-06); a page without i18n.js: English
  const t = (k, v) => window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const kindOf = t => ERR.test(t) ? "error" : OK.test(t) ? "success" : "info";
  let box = null;
  const ensure = () => {
    if (box && box.isConnected) return box;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    box = document.createElement("div"); box.id = "hyToasts"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
    box.addEventListener("mouseenter", () => { fan = true; live().forEach(el => clearTimeout(el._t)); lay(); });
    box.addEventListener("mouseleave", () => { fan = false; const L = live(); L.forEach((el, i) => { if (!el._sticky) { el._ms = 1800 + (L.length - 1 - i) * 500; life(el); } }); lay(); });   // the oldest first
    return box;
  };
  // where each card stands: index 0 is the newest, in front. Folded, the older ones step back behind it: 5 % smaller each and 8 px HIGHER,
  // so their top edge peeks above the front one (owner 2026-10-06: «what lies under the front notification lies above it, not below»),
  // three at most; fanned out (pointer on the stack) they stand in a list under the newest. All cards take the widest one's width.
  let fan = false;
  const live = () => [...box.children].filter(el => !el._gone).reverse();
  const lay = () => {
    if (!box) return; const L = live();
    // measured with the whole window as room (centred at 50 %, the box alone would only have half of it)
    box.style.setProperty("--ht-w", "auto"); box.style.left = "0"; box.style.maxWidth = "none"; L.forEach(el => { el.style.width = "max-content"; el.style.position = "relative"; });
    const w = Math.min(560, innerWidth - 32, Math.max(280, ...L.map(el => el.offsetWidth + 1)));
    box.style.left = box.style.maxWidth = ""; L.forEach(el => { el.style.width = ""; el.style.position = ""; });
    box.style.setProperty("--ht-w", w + "px");
    let y = 0; const PEEK = 8, base = Math.min(2, L.length - 1) * PEEK;   // the room the older edges take above the front card
    L.forEach((el, i) => {
      const h = el.offsetHeight; el.classList.toggle("behind", i > 0); el.classList.toggle("fan", fan); el.style.zIndex = 100 - i;   /* hy-allow: z-layer the order of the toasts inside #hyToasts (its own stacking context), newest on top */
      if (fan) { el.style.transform = `translateY(${y}px)`; el.style.opacity = 1; y += h + 8; }
      else { el.style.transform = `translateY(${base - Math.min(i, 2) * PEEK}px) scale(${1 - Math.min(i, 3) * .05})`; el.style.opacity = i < 3 ? 1 - i * .15 : 0; }   // scaled from its top: the edge shows above
      el.style.pointerEvents = fan || i === 0 ? "" : "none";
    });
    const front = L[0] ? L[0].offsetHeight : 0;
    box.style.setProperty("--ht-h", (fan ? Math.max(0, y - 8) : front + base) + "px");
  };
  const leave = el => {
    if (el._gone) return; el._gone = true; clearTimeout(el._t);
    el.style.opacity = 0; el.style.transform = (el.style.transform || "") + " translateY(-10px) scale(.96)"; el.style.pointerEvents = "none";
    setTimeout(() => { el.remove(); if (!live().length) fan = false; lay(); }, 320); lay();
  };
  const life = el => { clearTimeout(el._t); if (!fan) el._t = setTimeout(() => leave(el), el._ms); };
  window.hyToast = (text, kind, opt) => {
    text = String(text || "").trim(); if (!text) return; opt = opt || {};
    // inside an iframe of the same page family (the canvas in the library): the top page shows it, one stack for both
    try { if (window.parent !== window && window.parent.hyToast) return window.parent.hyToast(text, kind, opt); } catch {}
    const b = ensure(); kind = kind || kindOf(text);
    const same = [...b.children].find(el => !el._gone && el._text === text);   // the same words again: that one stays longer, no copy
    if (same) { if (!same._sticky) life(same); return same; }
    const el = document.createElement("div"); el.className = "ht " + kind; el._text = text; el._ms = kind === "error" ? 5200 : 3200;
    el.innerHTML = "<i></i><span></span>"; el.lastChild.textContent = text; el._sticky = !!opt.sticky;
    // buttons on the note (owner 2026-10-06, «Move to page»: «Open» and «Undo»): opt.actions [{ label, fn }]; a press runs it and the note goes
    (opt.actions || []).forEach(a => {
      const b = document.createElement("button"); b.type = "button"; b.className = "ab"; b.textContent = a.label;
      b.addEventListener("click", ev => { ev.stopPropagation(); leave(el); try { a.fn(); } catch (er) { console.error(er); } }); el.appendChild(b);
    });
    if (opt.actions && opt.actions.length) { el._ms = 6500; el.classList.add("act"); }   // time to read it and reach a button
    if (el._sticky) {   // it stays: only its × takes it away
      const x = document.createElement("button"); x.className = "x"; x.type = "button"; x.title = t("Close"); x.setAttribute("aria-label", t("Close notification"));
      x.innerHTML = window.hyIcon ? window.hyIcon("close", 12, 2.4) : "";
      x.addEventListener("click", () => leave(el)); el.appendChild(x);
    } else {
      el.addEventListener("click", () => leave(el));
    }
    // it comes in UNDER the stack and rises into the front while the others step back and up (owner 2026-10-06: «new ones don't appear
    // on top covering everything, they appear below and then fold up there»)
    const under = (b.offsetHeight || 0) + 10;
    b.appendChild(el); el.style.opacity = 0; el.style.transform = `translateY(${under}px) scale(.96)`;
    requestAnimationFrame(() => requestAnimationFrame(lay));
    const L = live(), passing = L.filter(x => !x._sticky);
    if (L.length > 5 && passing.length) leave(passing[passing.length - 1]);   // five at most: the oldest passing one makes room, a sticky one stays
    if (!el._sticky) { el._ms += Math.min(3, L.length - 1) * 400; life(el); }   // the older ones keep their own time, so they go one after another
    return el;
  };
})();
