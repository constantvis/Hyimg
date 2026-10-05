// One kind of notification for every Hyimg page (owner 2026-10-04: the canvas showed its notes at the top and the library at the bottom,
// in two looks). A stack at the top centre of the window, as notifications on the iPhone's lock screen (owner 2026-10-05: «one after
// another, the top one does not leave at once»): the newest stands in front, the older ones tuck in behind it a little lower and smaller,
// the pointer on the stack fans it out into a list and holds every timer; each leaves after its own time, the oldest first.
// Glass with blur like the panels; the colour says what it is: error red, news or a note blue, success green; light and dark themes.
// hyToast(text, kind?, {sticky}?) — kind "error" | "info" | "success"; without it the words decide. A sticky one (something to act on,
// owner 2026-10-04: «key notes that matter in the moment can stay, with a × on the right to close») stays until its × is pressed. The canvas inside the library page sends its
// notes up here, so one stack shows everything. They stand in the window's middle, an open library or not (owner 2026-10-04); --toast-x on <html> can move them, 50% by default.
(() => {
  if (window.hyToast) return;
  const css = `
#hyToasts { position: fixed; top: var(--toast-top, 14px); left: var(--toast-x, 50%); transform: translateX(-50%); z-index: 1000; pointer-events: none;
  width: var(--ht-w, 320px); max-width: calc(100vw - 32px); height: var(--ht-h, 0px); transition: top .3s cubic-bezier(.32,.72,0,1); }
#hyToasts:not(:empty) { pointer-events: auto; }
#hyToasts .ht { --k: var(--ht-info); position: absolute; transform-origin: 50% 100%; left: 0; right: 0; top: 0; box-sizing: border-box; display: flex; align-items: center; gap: 10px; padding: 9px 14px 9px 12px; border-radius: 12px;
  font: 500 13px/1.4 var(--sans, -apple-system, system-ui, sans-serif); color: var(--ink, #fafafa); cursor: default;
  background: color-mix(in srgb, var(--k) 14%, color-mix(in srgb, var(--panel, #18181b) 86%, transparent));
  border: 1px solid color-mix(in srgb, var(--k) 38%, var(--line, rgba(255,255,255,.12)));
  -webkit-backdrop-filter: blur(20px) saturate(1.5); backdrop-filter: blur(20px) saturate(1.5); box-shadow: 0 10px 32px rgba(0,0,0,.28);
  opacity: 0; transform: translateY(-14px) scale(.96); transition: opacity .32s cubic-bezier(.32,.72,0,1), transform .42s cubic-bezier(.32,.72,0,1); }
#hyToasts .ht > * { transition: opacity .25s ease; }
#hyToasts .ht.behind:not(.fan) > * { opacity: 0; }   /* a card tucked behind shows only its edge, its words come back when the stack fans out */
#hyToasts .ht i { flex: none; width: 8px; height: 8px; border-radius: 50%; background: var(--k); box-shadow: 0 0 0 3px color-mix(in srgb, var(--k) 25%, transparent); }
#hyToasts .ht.error { --k: var(--ht-error); } #hyToasts .ht.success { --k: var(--ht-success); }
#hyToasts .ht .x { flex: none; width: 22px; height: 22px; margin: -3px -6px -3px 2px; padding: 0; border: 0; border-radius: 6px; background: transparent; color: inherit; opacity: .6;
  display: grid; place-items: center; cursor: pointer; font: inherit; } #hyToasts .ht .x:hover { opacity: 1; background: color-mix(in srgb, currentColor 12%, transparent); }
:root { --ht-info: #0a84ff; --ht-success: #30d158; --ht-error: #ff453a; }
:root[data-theme="light"] { --ht-info: #007aff; --ht-success: #248a3d; --ht-error: #d70015; }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { --ht-info: #007aff; --ht-success: #248a3d; --ht-error: #d70015; } }
@media (prefers-reduced-motion: reduce) { #hyToasts .ht { transition: opacity .15s; } }`;
  const ERR = /не получилось|не удалось|не сохранил|не сохранен|не загрузил|не записан|не ответил|не удалить|сбросила|ошибк|нельзя|⚠/i;
  const OK = /^(версия сохранена|картинка скопирована|сохранено|готово)|снова на холсте/i;
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
  // where each card stands: index 0 is the newest, in front. Folded, the older ones sit 9 px lower each, 5 % smaller, three at most;
  // fanned out (pointer on the stack) they stand in a list under the newest. All cards take the widest one's width, so the edges line up.
  let fan = false;
  const live = () => [...box.children].filter(el => !el._gone).reverse();
  const lay = () => {
    if (!box) return; const L = live();
    // measured with the whole window as room (centred at 50 %, the box alone would only have half of it)
    box.style.setProperty("--ht-w", "auto"); box.style.left = "0"; box.style.maxWidth = "none"; L.forEach(el => { el.style.width = "max-content"; el.style.position = "relative"; });
    const w = Math.min(560, innerWidth - 32, Math.max(280, ...L.map(el => el.offsetWidth + 1)));
    box.style.left = box.style.maxWidth = ""; L.forEach(el => { el.style.width = ""; el.style.position = ""; });
    box.style.setProperty("--ht-w", w + "px");
    let y = 0; const fh = L[0] ? L[0].offsetHeight : 0;
    L.forEach((el, i) => {
      const h = el.offsetHeight; el.classList.toggle("behind", i > 0); el.classList.toggle("fan", fan); el.style.zIndex = 100 - i;
      if (fan) { el.style.transform = `translateY(${y}px)`; el.style.opacity = 1; y += h + 8; }
      else { el.style.transform = `translateY(${i ? fh - h + Math.min(i, 3) * 9 : 0}px) scale(${1 - i * .05})`; el.style.opacity = i < 3 ? 1 - i * .18 : 0; }   // an older card's bottom edge peeks under the front one's
      el.style.pointerEvents = fan || i === 0 ? "" : "none";
    });
    const front = L[0] ? L[0].offsetHeight : 0;
    box.style.setProperty("--ht-h", (fan ? Math.max(0, y - 8) : front + Math.min(2, L.length - 1) * 9) + "px");
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
    if (el._sticky) {   // it stays: only its × takes it away
      const x = document.createElement("button"); x.className = "x"; x.type = "button"; x.title = "Закрыть"; x.setAttribute("aria-label", "Закрыть уведомление");
      x.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      x.addEventListener("click", () => leave(el)); el.appendChild(x);
    } else {
      el.addEventListener("click", () => leave(el));
    }
    b.appendChild(el); el.style.opacity = 0; el.style.transform = "translateY(-14px) scale(.96)";
    requestAnimationFrame(() => requestAnimationFrame(lay));   // it drops in at the front, the others step back
    const L = live(), passing = L.filter(x => !x._sticky);
    if (L.length > 5 && passing.length) leave(passing[passing.length - 1]);   // five at most: the oldest passing one makes room, a sticky one stays
    if (!el._sticky) { el._ms += Math.min(3, L.length - 1) * 400; life(el); }   // the older ones keep their own time, so they go one after another
    return el;
  };
})();
