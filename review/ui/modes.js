// The board's modes in its dock (owner 2026-10-06: «in the bottom menu let's add a toggle like in Figma: Board mode, Image mode, Dev mode,
// and 3D studio, but 3D studio turns on only when we entered a 3D object»). One switch, the app's one choice component (ui/look.css .seg,
// its thumb from ui/seg.js): Board is Hyimg's own and always there; every other mode is a plugin's (owner: «dev studio and html are a
// plugin too»): the image frames give Image, the 3D studio 3D, Dev studio Dev. A mode a plugin does not bring is not shown.
// Made as Figma's (owner, same day, with a Figma screenshot: «look how Figma's switch is made, it's on the right and only the icon;
// active»): at the right end of the dock after a thin divider, also while an editor owns the dock; icons only at every width, in a group
// of their own (a raised ground in the dark look, a slightly darker one in the light), the chosen one a filled tile with its icon in the
// selection's blue, the others muted, a disabled one dimmed. The name is in a small tooltip over the segment (the image studio's tooltip
// plate), a disabled one's says what enables it. Each segment is as big as the dock's other icon buttons; round in the round look, the
// shared row radius (--hy-row-r) in «pro».
//
// A plugin says, through HY.mode(key, def):
//   label, icon        the segment's short name (Image, 3D, Dev) and its 16 px line icon (svg markup)
//   name               its full name in the tooltip and for a screen reader (owner 2026-10-08: Image Studio, 3D Studio, Dev Studio;
//                      working inside an object is a Studio, on the canvas the Board); the label when not given
//   order              its place after Board (Image 10, Dev 20, 3D 30)
//   title, hint        what it does when it can be entered (aria-description), and when it cannot: what enables it (the tooltip says it)
//   isOpen()           its editor is open now (the switch shows it chosen)
//   target(ids)        the card the mode would open for this selection, or null: the segment is enabled when there is one
//   enter(id), leave() open its editor for that card; close it the way its own Done does
//   card()             optional: the card its open editor works on (else the live card .plg-live, the card it was entered with, the
//                      one selected card)
//   color              optional: the Studio's colour (a CSS colour or var(), Image Studio's purple var(--frame)); its segment, chosen,
//                      wears it instead of the selection's blue (owner 2026-10-09: «вроде же бы в цвет режима должно быть?»). Board and
//                      a Studio without one keep the blue. While that Studio is open the colour is the whole window's: <html> gets
//                      data-studio="<key>" and --hy-studio, and --sel, --hy-sel and the notes' info colour are it, so every chosen,
//                      picked or primary thing of the app inherits it, a dialog's action button too (ui/confirm.js; owner 2026-10-09:
//                      «опять мы что-то выделяем, у нас это синего цвета вместо зеленого ... чтобы у нас все режимы соответствовали»)
// The switch follows what happens anyway (a double click, Esc, Done): the board calls sync() after each render and when a plugin's editor
// takes the dock or gives it back (HY.dock), and a plugin may call HY.modeChanged(). Board leaves the open editor. A disabled mode stays
// in its place, dimmed. A dock too narrow for all its buttons keeps only the modes that can be entered now.
// While a mode is open the card it edits is lifted (ui/editlift.js, owner 2026-10-08): the board's selection around it hidden, a shadow
// under it, the rest of the board a little dimmer; every plugin's mode gets it from here.
//   const M = hyModes({ dock, sel: () => [...ids], toast, t, rect: id => {x, y, w, h} })   M.add(key, def)   M.sync()   M.enter(key, ids?)   M.el
(() => {
  if (window.hyModes) return;
  const EASE = "cubic-bezier(.32,.72,0,1)";
  // the board: the place where cards lie (ui/icons.js «board», the same as a board in Home's list)
  const BOARD_IC = () => (window.hyIcon ? window.hyIcon("board", 16) : "");
  const css = `
:root { --mode-g: color-mix(in srgb, var(--ink) 6%, transparent); --mode-on: var(--panel); --mode-on-sh: 0 1px 2px rgba(0,0,0,.14), 0 0 0 1px var(--line); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --mode-g: var(--raise); --mode-on: color-mix(in srgb, var(--ink) 14%, var(--raise)); --mode-on-sh: none; } }
:root[data-theme="dark"] { --mode-g: var(--raise); --mode-on: color-mix(in srgb, var(--ink) 14%, var(--raise)); --mode-on-sh: none; }
/* the right end of the dock, after everything else (an editor's own buttons too), behind a hairline like the dock's other separators */
#modesw { order: 99; display: inline-flex; align-items: center; gap: 6px; flex: none; }
#modesw > .msep { width: 1px; height: 18px; background: var(--line); flex: none; margin-right: 2px; }
#dock.plg-mode > #modesw { display: inline-flex !important; }
/* the group: its segments side by side, the group as tall as the dock's icon buttons (34 px); the chosen thumb var(--hy-seg-pad) in from
   the track on every side, as every .seg (owner 2026-10-06: it touched the track's top and bottom) */
#dock #modes { padding: var(--hy-seg-pad, 3px); gap: 0; background: var(--mode-g); border-radius: 999px; }
#dock #modes > .st { background: var(--mode-on); box-shadow: var(--mode-on-sh); }
#dock #modes > button { width: calc(38px - 2 * var(--hy-seg-pad, 3px)); height: calc(34px - 2 * var(--hy-seg-pad, 3px)) !important; padding: 0 !important; justify-content: center; background: transparent !important; color: var(--sub) !important;
  transition: color .2s ${EASE}, opacity .2s ${EASE}; }
:root[data-ui="studio"] #dock #modes > button { width: calc(32px - 2 * var(--hy-seg-pad, 3px)); }
#dock #modes > button:hover { color: var(--ink) !important; }
#dock #modes > button[aria-pressed=true] { color: var(--hy-mode-c, var(--sel)) !important; }
/* the open Studio's colour on the whole window (see color above); :not(#_) outranks the theme's :root[data-theme] of ui/tokens.css */
:root[data-studio]:not(#_) { --sel: var(--hy-studio); --hy-sel: var(--hy-studio); --ht-info: var(--hy-studio); }
#dock #modes > button[aria-disabled=true] { opacity: .38; cursor: default; }
#dock #modes > button[aria-disabled=true]:hover { color: var(--sub) !important; }
#dock #modes > button svg { flex: none; display: block; }
#dock #modes.few > button[aria-disabled=true] { display: none !important; }
:root[data-shape=pro] #dock #modes { border-radius: var(--hy-row-r, 8px) !important; }
:root[data-shape=pro] #dock #modes > :is(.st, button) { border-radius: calc(var(--hy-row-r, 8px) - var(--hy-seg-pad, 3px)) !important; }   /* concentric with the track */
/* the tooltip: the image studio's (hyimg-frames editor #tip), a small plate over the segment; the name, and what enables a disabled one.
   On the menus' layer, over an editor's panels (the 3D studio's are 60, 61); the frame editor lifts it with the dock (hyimg-frames) */
#modetip { position: fixed; left: 0; top: 0; z-index: 79; display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 12px; white-space: nowrap;
  border: 1px solid var(--line); border-radius: 999px; background: color-mix(in srgb, var(--panel) 86%, transparent); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px);
  box-shadow: var(--plate-sh, 0 8px 24px rgba(0,0,0,.35)); color: var(--ink); font: 500 12px var(--sans); pointer-events: none; opacity: 0;
  transition: opacity .16s ${EASE}, transform .26s ${EASE}; }
#modetip.on { opacity: 1; }
#modetip .mth { color: var(--sub); font-weight: 400; }
:root[data-shape=pro] #modetip { border-radius: 11px; }
@media (prefers-reduced-motion: reduce) { #dock #modes > button, #modetip { transition: none; } }`;
  window.hyModes = function ({ dock, sel, t = k => k, rect = null }) {
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const LIFT = rect && window.hyEditLift ? window.hyEditLift({ rect }) : null;
    let liftK = "board", entered = { k: "", id: null };
    const M = new Map([["board", { label: t("Board"), icon: BOARD_IC(), order: 0, title: t("Board: every card, the canvas itself"), board: true }]]);
    const wrap = document.createElement("div"), el = document.createElement("div");
    wrap.id = "modesw"; wrap.innerHTML = `<span class="msep" aria-hidden="true"></span>`;
    el.className = "seg"; el.id = "modes"; el.setAttribute("role", "group"); el.setAttribute("aria-label", t("Mode"));
    wrap.appendChild(el); dock.appendChild(wrap);
    const tip = document.createElement("div"); tip.id = "modetip"; tip.setAttribute("role", "tooltip"); tip.setAttribute("aria-hidden", "true"); document.body.appendChild(tip);
    let raf = 0, waiting = null;
    const defs = () => [...M.entries()].sort((a, b) => (a[1].order || 0) - (b[1].order || 0));
    const safe = (f, d) => { try { return f(); } catch (e) { console.error(e); return d; } };
    const openKey = () => { for (const [k, d] of defs()) if (!d.board && d.isOpen && safe(() => d.isOpen(), false)) return k; return "board"; };
    function build() {
      el.querySelectorAll(":scope > button").forEach(b => b.remove());
      for (const [k, d] of defs()) {
        const b = document.createElement("button"); b.type = "button"; b.dataset.mode = k;
        b.innerHTML = d.icon || "";   // the icon alone: the name is the tooltip's and the screen reader's
        const nm = d.name || d.label || k; b.setAttribute("aria-label", nm); b.dataset.name = nm; el.appendChild(b);
        if (d.color) b.style.setProperty("--hy-mode-c", d.color);   // the Studio's colour when chosen
      }
      if (window.hySeg) window.hySeg(el);
      sync(true); fit();
    }
    // what is chosen and what can be entered, from the open editor and the selection
    function sync(now) {
      if (!now) { if (!raf) raf = requestAnimationFrame(() => { raf = 0; sync(true); }); return; }
      const open = openKey(), ids = safe(sel, []); let moved = false;
      for (const b of el.querySelectorAll(":scope > button")) {
        const k = b.dataset.mode, d = M.get(k); if (!d) continue;
        const on = k === open, can = d.board || on || !!safe(() => d.target && d.target(ids), null);
        if (b.getAttribute("aria-pressed") !== String(on)) b.setAttribute("aria-pressed", String(on));
        if (b.getAttribute("aria-disabled") !== String(!can)) { b.setAttribute("aria-disabled", String(!can)); moved = true; }
        // the tooltip: the name; on a disabled one also what enables it
        const hint = can ? "" : (d.hint || d.title || ""), desc = can ? (d.title || "") : hint;
        if (b.dataset.tip !== (hint || b.dataset.name)) b.dataset.tip = hint || b.dataset.name;
        if (desc) { if (b.getAttribute("aria-description") !== desc) b.setAttribute("aria-description", desc); } else b.removeAttribute("aria-description");
        if (tipFor === b) showTip(b, true);
      }
      if (moved && el.classList.contains("few")) fit();
      paint(open);
      lift(open, ids);
    }
    // the open Studio's colour on <html> (data-studio, --hy-studio), gone on the board or in a Studio that brings none
    function paint(open) {
      const d = open !== "board" && M.get(open), c = d && d.color ? String(d.color) : "", r = document.documentElement;
      if ((r.dataset.studio || "") === (c ? open : "") && r.style.getPropertyValue("--hy-studio") === c) return;
      if (c) { r.dataset.studio = open; r.style.setProperty("--hy-studio", c); } else { delete r.dataset.studio; r.style.removeProperty("--hy-studio"); }
    }
    // the card the open mode edits: its own word, the live card, the card it was entered with, the one selected card
    function cardOf(k, ids) {
      const d = M.get(k), own = safe(() => d && d.card ? d.card() : null, null); if (own) return own;
      const live = document.querySelector("#items .plg-live[data-id]"); if (live) return live.dataset.id;
      if (entered.k === k && entered.id) return entered.id;
      return ids.length === 1 ? ids[0] : null;
    }
    // that card lifted while the mode is open, set down when it closes; the card is the one found when it opened, unless the mode names
    // another (its frame turned into a new card)
    function lift(open, ids) {
      if (!LIFT) return;
      if (open !== liftK) { liftK = open; return LIFT.set(open === "board" ? null : cardOf(open, ids), open); }
      if (open === "board") return;
      const d = M.get(open), own = safe(() => d && d.card ? d.card() : null, null);
      if (own && own !== LIFT.id) LIFT.set(own, open); else if (!LIFT.id) LIFT.set(cardOf(open, ids), open); else LIFT.place();
    }
    // a dock too narrow for all its buttons (a narrow window, the library open beside the board): the modes that cannot be entered now
    // step out (Board and the chosen one stay)
    let fr = 0;
    function fit(now) {
      if (!now) { if (!fr) fr = requestAnimationFrame(() => { fr = 0; fit(true); }); return; }
      if (!dock.isConnected || !dock.offsetWidth) return;
      el.classList.remove("few");
      if (dock.scrollWidth > dock.clientWidth + 1) el.classList.add("few");
    }
    // the tooltip over a segment: after a short rest under the pointer, at once while another was just shown (as the image studio's)
    let tipFor = null, tipT = 0, tipLast = 0;
    function showTip(b, keep) {
      const name = b.dataset.name || "", more = b.dataset.tip && b.dataset.tip !== name ? b.dataset.tip : "";
      tip.textContent = name;
      if (more) { const m = document.createElement("span"); m.className = "mth"; m.textContent = more; tip.appendChild(m); }
      const r = b.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
      const x = Math.max(8, Math.min(innerWidth - tw - 8, r.left + r.width / 2 - tw / 2)), y = Math.max(8, r.top - 10 - th);
      if (!tip.classList.contains("on") && !keep) { tip.style.transition = "none"; tip.style.transform = `translate(${x}px, ${y + 4}px)`; tip.offsetWidth; tip.style.transition = ""; }
      tip.style.transform = `translate(${x}px, ${y}px)`; tip.classList.add("on"); tipFor = b;
    }
    function hideTip() { clearTimeout(tipT); tipT = 0; if (tip.classList.contains("on")) tipLast = performance.now(); tip.classList.remove("on"); tipFor = null; }
    el.addEventListener("pointerover", e => {
      const b = e.target.closest("button[data-mode]"); if (!b || b === tipFor) return;
      clearTimeout(tipT);
      const quick = tip.classList.contains("on") || performance.now() - tipLast < 400;
      tipT = setTimeout(() => showTip(b), quick ? 0 : 420);
    });
    el.addEventListener("pointerleave", hideTip);
    addEventListener("pointerdown", hideTip, true);
    // enter mode k for these cards (the selection when not given), as its segment does; false when k is not there or takes none of them
    function enter(k, given) {
      const d = M.get(k), open = openKey(); if (!d || k === open) return false;
      const ids = given || safe(sel, []), id = d.board ? null : safe(() => d.target(ids), null);
      if (!d.board && !id) return false;
      clearInterval(waiting); entered = { k, id };
      const go = () => { if (!d.board) safe(() => d.enter(id)); sync(); };
      if (open === "board") { go(); return true; }
      // another editor is open: it closes as its own Done does (it may ask first, the frame editor about unsaved changes), then this one opens
      safe(() => M.get(open).leave());
      if (d.board) { sync(); return true; }
      let n = 0; waiting = setInterval(() => { if (openKey() === "board") { clearInterval(waiting); go(); } else if (++n > 100) clearInterval(waiting); }, 40);
      return true;
    }
    el.addEventListener("click", e => {
      const b = e.target.closest("button[data-mode]"); if (!b) return;
      e.stopPropagation();
      if (b.getAttribute("aria-disabled") !== "true") enter(b.dataset.mode);
    });
    new MutationObserver(() => { sync(); fit(); }).observe(dock, { attributes: true, attributeFilter: ["class"] });
    // not for the zoom's percent (#zl), rewritten on every frame of a zoom: each fit there forced the board's whole layout (2026-10-08)
    new MutationObserver(ms => { if (ms.some(m => !(m.target.closest ? m.target : m.target.parentElement)?.closest("#zl"))) fit(); })
      .observe(dock, { childList: true, subtree: true, characterData: true });
    const ro = new ResizeObserver(() => fit()); ro.observe(dock.parentElement || dock); ro.observe(dock);   // the window, and the library's edge (--inset) narrowing the dock
    addEventListener("resize", () => fit());
    build();
    return {
      el,
      add(key, def) { if (!key || key === "board" || !def) return; M.set(key, def); build(); },
      sync: () => sync(),
      // a mode entered by other means than its segment (a double click on a picture enters Image, owner 2026-10-07): true when it goes in
      enter: (k, ids) => enter(k, ids),
      get open() { return openKey(); },
    };
  };
})();
