// One dock for the board and the three Studios (owner 2026-10-10 on round 18, r18-dock.html, ★ yes): every icon button 36 × 34 with no
// plate under it, as the Studios had them, a hairline between the groups, one order everywhere:
//   create | tools | history (Undo, Redo) | view % | the Studio's own (Snapshot, Actions) | the switch of Studios
// The board's dock was 38 × 34 on round plates and 3D Studio's 34 and 38 on plates; Image Studio had no Undo, 3D and Dev no view %
// and no Actions. What every dock shares lives here, each dock (canvas.html with ui/boarddock.js, and the plugins) only calls it:
//   class "hy-dkb" on an icon button 36 × 34, no plate, the raised ground under the pointer; .on / .pri / [aria-pressed=true] keep their fill
//   <span class="sep">               the hairline between two groups
//   hyDock.menu(btn, el, o)          a list that opens above a dock button (the board's «+», 3D Studio's «+» Add): the app's menu items
//                                    (ui/menu.js hyMenuItem), Image Studio's tool list look; o.fill(el) before it opens, o.pick(item) on a
//                                    click on an item; Esc, a click elsewhere or the button again close it; ↑ ↓ ↵ are ui/menu.js's
//   hyDock.steps({undo, redo, name}) the step's name (owner 2026-10-10: «Я бы вот эти элементы делал по наведению, то есть чтобы оно
//                                    изначально не расширяло этот элемент. У всех доков»): over Undo or Redo under the pointer a small plate
//                                    above the button says «Undo · Move Bracket ⌘Z»; after ⌘Z or ⇧⌘Z done(dir) shows the same plate for 2 s
//                                    over the button of that direction. The plate floats over the dock and never widens it. name(dir) is the
//                                    step that button would take now ("undo" | "redo"), "" or null when none
//   hyDock.acts(open)                the dock's Actions button, «⌘ Actions ⌘K», Image Studio's (hyimg-image-studio imgframe.js)
(() => {
  if (window.hyDock) return;
  const t = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const EASE = "cubic-bezier(.32,.72,0,1)";
  const css = `
:root:not([data-ui="studio"]) #dock :is(button.ic, button.hy-dkb) { width: 36px !important; height: 34px !important; padding: 0 !important; justify-content: center; flex: none; }
:root:not([data-ui="studio"]) #dock :is(button.ic, button.hy-dkb):not(.on, .pri, [aria-pressed=true]) { background: transparent !important; }
:root:not([data-ui="studio"]) #dock :is(button.ic, button.hy-dkb):not(.on, .pri, [aria-pressed=true], :disabled):hover { background: var(--raise) !important; }
#dock :is(button.ic, button.hy-dkb):disabled { opacity: .4; }
#dock .sep { width: 1px; height: 18px; background: var(--line); margin: 0 4px; flex: none; }
#dock .dgrp { display: contents; }
#dock .dgrp:empty + .sep { display: none; }
/* the view's percent: a plate with its number, a click fits (the board: show all, ⇧1; a Studio: its card between its panels) */
#dock button.zlb { min-width: 56px; padding: 0 12px !important; justify-content: center; color: var(--ink) !important; font-variant-numeric: tabular-nums; }
#dock button.zlb .zl { color: inherit; padding: 0; min-width: 0; font-size: 13px; }
/* a list over a dock button: the app's menu (ui/look.css .menu items), Image Studio's tool list (hyimg-image-studio studiodock.js .ifly) */
.hy-dkmenu { position: fixed; z-index: 1210; min-width: 220px; padding: 6px; box-sizing: border-box; border: 1px solid var(--line); border-radius: 14px;
  background: color-mix(in srgb, var(--panel) 92%, transparent); -webkit-backdrop-filter: blur(18px) saturate(1.4); backdrop-filter: blur(18px) saturate(1.4);
  box-shadow: var(--hy-sh-pop, 0 16px 40px rgba(0,0,0,.45)); transform-origin: 18px 100%; display: grid; gap: 0; }
.hy-dkmenu[hidden] { display: none !important; }
.hy-dkmenu.open { animation: hyDkIn .16s ${EASE}; }
@keyframes hyDkIn { from { opacity: 0; transform: translateY(6px) scale(.97); } }
.hy-dkmenu > button { display: flex; align-items: center; gap: 9px; width: 100%; height: 32px; padding: 0 10px; border: 0; border-radius: var(--hy-row-r, 9px);
  background: none; color: var(--sub); font: 500 13px var(--sans); text-align: left; cursor: default; white-space: nowrap; }
.hy-dkmenu > button:not(:disabled, [aria-disabled=true]):is(:hover, :focus-visible) { background: var(--raise); color: var(--ink); outline: none; }
.hy-dkmenu > button > svg { flex: none; opacity: .75; }
:root[data-shape=pro] .hy-dkmenu { border-radius: 11px; }
/* the step's name over Undo or Redo: the switch's tooltip plate (ui/modes.js #modetip), floating, so the dock keeps its width */
#hydkstep { position: fixed; left: 0; top: 0; z-index: 79; display: flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; white-space: nowrap;
  border: 1px solid var(--line); border-radius: 999px; background: color-mix(in srgb, var(--panel) 86%, transparent); -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px); box-shadow: var(--plate-sh, 0 8px 24px rgba(0,0,0,.35)); color: var(--ink); font: 500 12px var(--sans); pointer-events: none; opacity: 0;
  transition: opacity .16s ${EASE}, transform .26s ${EASE}; }
#hydkstep.on { opacity: 1; }
#hydkstep .sw { color: var(--sub); font-weight: 400; }
#hydkstep hy-kbd { margin-left: 4px; }
:root[data-shape=pro] #hydkstep { border-radius: 11px; }
@media (prefers-reduced-motion: reduce) { .hy-dkmenu.open { animation: none; } #hydkstep { transition: none; } }`;
  const st = document.createElement("style"); st.id = "hy-dock-css"; st.textContent = css; (document.head || document.documentElement).appendChild(st);

  // ---- a list over a dock button ----------------------------------------------------------------------------------------------------
  let openMenu = null;   // the one list open now
  function menu(btn, el, o = {}) {
    el.classList.add("menu", "hy-dkmenu"); el.setAttribute("role", "menu"); el.hidden = true;
    if (!el.isConnected) document.body.appendChild(el);
    btn.setAttribute("aria-haspopup", "menu"); btn.setAttribute("aria-expanded", "false");
    const place = () => {
      const r = btn.getBoundingClientRect(), d = btn.closest("#dock") || btn, dr = d.getBoundingClientRect();
      el.style.left = Math.max(8, Math.min(innerWidth - el.offsetWidth - 8, r.left - 6)) + "px";
      el.style.top = Math.max(8, dr.top - 8 - el.offsetHeight) + "px"; el.style.bottom = "auto";
    };
    const M = {
      el, place,
      get isOpen() { return !el.hidden; },
      open() {
        if (openMenu && openMenu !== M) openMenu.close();
        if (o.fill) o.fill(el);
        el.hidden = false; el.classList.add("open"); el.dataset.hymenu = "open"; btn.setAttribute("aria-expanded", "true"); openMenu = M; place();
      },
      close() {
        if (el.hidden) return;
        el.hidden = true; el.classList.remove("open"); delete el.dataset.hymenu; btn.setAttribute("aria-expanded", "false"); if (openMenu === M) openMenu = null;
        if (window.hyMenuSubClose) window.hyMenuSubClose();
      },
      toggle() { M.isOpen ? M.close() : M.open(); },
    };
    btn.addEventListener("click", e => { e.stopPropagation(); M.toggle(); });
    btn.addEventListener("pointerdown", e => e.stopPropagation());
    el.addEventListener("pointerdown", e => e.stopPropagation());
    el.addEventListener("click", e => {
      e.stopPropagation();
      const it = e.target.closest("button"); if (!it || it.disabled || it.getAttribute("aria-disabled") === "true") return;
      M.close(); if (o.pick) o.pick(it, e);
    });
    return M;
  }
  // a press elsewhere and Esc close the open list first, before the board or a Studio sees them
  addEventListener("pointerdown", e => { if (openMenu && !openMenu.el.contains(e.target)) openMenu.close(); }, true);
  addEventListener("keydown", e => { if (e.key === "Escape" && openMenu) { e.preventDefault(); e.stopImmediatePropagation(); openMenu.close(); } }, true);
  addEventListener("resize", () => { if (openMenu) openMenu.place(); });

  // ---- the step's name over Undo and Redo --------------------------------------------------------------------------------------------
  let plate = null, plateFor = null, plateT = 0, hoverT = 0;
  const KEY = { undo: "⌘Z", redo: "⇧⌘Z" };
  function showPlate(btn, dir, name, keyed) {
    if (!btn || !btn.isConnected || !btn.getClientRects().length) return;
    if (!plate) { plate = document.createElement("div"); plate.id = "hydkstep"; plate.setAttribute("role", "status"); plate.setAttribute("aria-live", "polite"); document.body.appendChild(plate); }
    plate.textContent = "";
    const w = document.createElement("span"); w.className = "sw"; w.textContent = t(dir === "undo" ? "Undo" : "Redo") + (name ? " ·" : ""); plate.appendChild(w);
    if (name) { const b = document.createElement("span"); b.className = "sn"; b.textContent = name; plate.appendChild(b); }
    if (keyed) { const k = document.createElement("hy-kbd"); k.setAttribute("size", "s"); k.textContent = KEY[dir]; plate.appendChild(k); }   // the app's key cap (ui/hy)
    const r = btn.getBoundingClientRect(), pw = plate.offsetWidth, ph = plate.offsetHeight;
    const x = Math.max(8, Math.min(innerWidth - pw - 8, r.left + r.width / 2 - pw / 2)), y = Math.max(8, r.top - 10 - ph);
    if (!plate.classList.contains("on")) { plate.style.transition = "none"; plate.style.transform = `translate(${x}px, ${y + 4}px)`; plate.offsetWidth; plate.style.transition = ""; }
    plate.style.transform = `translate(${x}px, ${y}px)`; plate.classList.add("on"); plate.dataset.dir = dir; plateFor = btn;
  }
  function hidePlate(btn) {
    if (btn && plateFor !== btn) return;
    clearTimeout(plateT); plateT = 0; if (plate) plate.classList.remove("on"); plateFor = null;
  }
  function steps({ undo, redo, name }) {
    const nm = dir => { try { return String(name(dir) || "").trim(); } catch (e) { console.error("step name", e); return ""; } };
    const btns = { undo, redo };
    for (const [dir, b] of Object.entries(btns)) {
      if (!b) continue;
      // the plate is the button's tooltip now: its words move to the screen reader, the key is on the plate
      if (b.title) { b.dataset.tipWas = b.title; b.removeAttribute("title"); }
      b.addEventListener("pointerenter", () => {
        clearTimeout(hoverT); clearTimeout(plateT); plateT = 0;
        hoverT = setTimeout(() => { if (b.matches(":hover")) showPlate(b, dir, nm(dir), true); }, plate && plate.classList.contains("on") ? 0 : 300);
      });
      b.addEventListener("pointerleave", () => { clearTimeout(hoverT); if (!plateT) hidePlate(b); });
      b.addEventListener("pointerdown", () => { clearTimeout(hoverT); });
    }
    return {
      // after ⌘Z (dir "undo") the step that went is the one Redo would bring back, after ⇧⌘Z the one Undo would take: its name for 2 s
      done(dir) {
        const b = btns[dir]; if (!b) return;
        const n = nm(dir === "undo" ? "redo" : "undo");
        clearTimeout(hoverT); showPlate(b, dir, n, false);
        clearTimeout(plateT); plateT = setTimeout(() => { plateT = 0; if (b.matches(":hover")) showPlate(b, dir, nm(dir), true); else hidePlate(b); }, 2000);
      },
      name: nm,
    };
  }

  // ---- the dock's Actions button ------------------------------------------------------------------------------------------------------
  function acts(open) {
    const b = document.createElement("button"); b.type = "button"; b.className = "wide dkacts"; b.dataset.a = "acts";
    b.title = t("Actions · ⌘K"); b.setAttribute("aria-label", t("Actions")); b.setAttribute("aria-pressed", "false");
    b.innerHTML = (window.hyIcon ? window.hyIcon("actions", 16, 1.85) : "") + `<span>${t("Actions")}</span><kbd>⌘K</kbd>`;
    b.addEventListener("pointerdown", e => e.stopPropagation());
    b.addEventListener("click", e => { e.stopPropagation(); if (open) open(); });
    return b;
  }

  window.hyDock = { menu, steps, acts, plate: () => plate };
})();
