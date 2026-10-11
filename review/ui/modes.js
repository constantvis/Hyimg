// The board's modes in its dock (owner 2026-10-06: «in the bottom menu let's add a toggle like in Figma: Board mode, Image mode, Dev mode,
// and 3D studio, but 3D studio turns on only when we entered a 3D object»). One switch, the app's one choice component (ui/look.css .seg,
// its thumb from ui/seg.js): Board is Hyimg's own and always there; every other mode is a plugin's (owner: «dev studio and html are a
// plugin too»): the image frames give Image, the 3D studio 3D, Dev studio Dev. A mode a plugin does not bring is not shown.
// Made as Figma's (owner, same day, with a Figma screenshot: «look how Figma's switch is made, it's on the right and only the icon;
// active»): at the right end of the dock after a thin divider, also while an editor owns the dock; icons only at every width, in a group
// of their own (a raised ground in the dark look, a slightly darker one in the light), the chosen one a filled tile with its icon in the
// selection's blue, the others muted, a disabled one dimmed. The name is in the app's tooltip over the segment (ui/hy/tooltip.js, was the image studio's tooltip
// plate), a disabled one's says what enables it. Each segment is as big as the dock's other icon buttons; round in the round look, the
// shared row radius (--hy-row-r) in «pro».
//
// A plugin says, through HY.mode(key, def):
//   label, icon        the segment's short name (Image, 3D, Dev) and its 16 px line icon (svg markup)
//   name               its full name in the tooltip and for a screen reader (owner 2026-10-08: Image Studio, 3D Studio, Dev Studio;
//                      working inside an object is a Studio, on the canvas the Board); the label when not given
//   order              its place after Board (Image 10, Dev 20, 3D 30)
//   title, hint        what it does when it can be entered (aria-description), and when it cannot: what enables it (the tooltip says it)
//   hintStudio         optional: the same while another Studio is open, where nothing can be selected (owner decision 2026-10-10: «Open a
//                      3D card to use 3D Studio»); hint when not given
//   pending()          optional: its work still being written after it left (Image Studio writes after it closes, owner decision
//                      2026-10-10): a promise of true once written, false when refused; null when nothing is on its way. leaveFirst waits
//                      for it (a page switch), false keeps the page
//   unsaved()          optional: true while leaving the page would lose work; a browser asks before it unloads (⌘R there is the
//                      browser's; in the app View › Reload Page saves first)
//   isOpen()           its editor is open now (the switch shows it chosen)
//   target(ids)        the card the mode would open for this selection, or null: the segment is enabled when there is one
//   enter(id), leave() open its editor for that card; close it the way its own Done does
//   card()             optional: the card its open editor works on (else the live card .plg-live, the card it was entered with, the
//                      one selected card)
//   fit()              optional: the Studio puts its card between its own panels itself (Image Studio's own camera); else Hyimg flies
//                      the board's camera there as the Studio opens and back as it closes (P4 S-61, owner decision 2026-10-10)
//   fit: false         the camera stays where it is
//   primary, hints     the Hint bar as the Studio opens (P4 S-29): every Studio's is V Select, C Annotation, its 1–2 own keys (hints,
//                      <hy-keyhint> items, words with the plugin's prefix) and Esc / ⌘↵ with the primary action's word (primary: "Save"
//                      or "Done"); showHint(items, ctx) optional: shows them in the Studio's own page and returns the handle
//   color              optional: the Studio's colour (a CSS colour or var(), Image Studio's purple var(--frame)); its segment, chosen,
//                      wears it instead of the selection's blue (owner 2026-10-09: «вроде же бы в цвет режима должно быть?»). Board and
//                      a Studio without one keep the blue. While that Studio is open the colour is the whole window's: <html> gets
//                      data-studio="<key>" and --hy-studio, and --sel, --hy-sel and the notes' info colour are it, so every chosen,
//                      picked or primary thing of the app inherits it, a dialog's action button too (ui/confirm.js; owner 2026-10-09:
//                      «опять мы что-то выделяем, у нас это синего цвета вместо зеленого ... чтобы у нас все режимы соответствовали»)
// The Studio's shell (owner 2026-10-11 on round 20, r20/studio-a.html «Одна оболочка», ♥ «беру»): what the three Studios share is drawn
// here, each Studio gives only its content (studios audit S-06, S-07, S-18):
//   doc()              the thing open in it: { name, path }. The crumb gains one step, the Studio's dot and the name, the path in its
//                      tooltip (Figma grows its crumbs by one step as it enters a component); the leave question (ui/confirm.js hyLeave)
//                      names it by the same name. A file's name is shown without its folder and extension (docName)
//   docMenu(rect)      optional: a click on that step (Image Studio's frame menu, under the step's rectangle)
//   rename(name)       optional: a double click on the step renames the thing in place (a name: ↵ applies, Esc puts it back, ⌘↵ the
//                      primary action, ui/typing.js)
// The switch follows what happens anyway (a double click, Esc, Done): the board calls sync() after each render and when a plugin's editor
// takes the dock or gives it back (HY.dock), and a plugin may call HY.modeChanged(). Board leaves the open editor. A disabled mode stays
// in its place, dimmed. A dock too narrow for all its buttons keeps only the modes that can be entered now; in a Studio the switch is always
// Board and the open Studio, nothing else (studios audit S-01, 2026-10-11: Image Studio's dock was 833 px and did not fit beside the library)
// While a mode is open the card it edits is lifted (ui/editlift.js, owner 2026-10-08): the board's selection around it hidden, a shadow
// under it, the rest of the board a little dimmer; every plugin's mode gets it from here.
// In any Studio the board around it is inert (P4 S-08, П4 audit 2026-10-10: a click beside the 3D or Dev card picked and moved the board's
// cards, a file dropped on it made hidden cards): a press, a double click or a right click on the board outside the open card does
// nothing, and a file or a card dragged over the board shows that it can't be dropped, the reason in a note. A Studio that takes drops
// itself says so with def.drop(e) -> true (Image Studio takes its own in its page, as layers). M.leaveFirst() asks the open Studio to leave
// its own way (it may ask about unsaved work) and resolves true once the board is back, false when it stayed (P4 S-09: a page switch)
// Moving from one Studio to another (P4 S-31) is the first one's own leave (it keeps the work: the last Esc, the Board segment and another
// Studio's segment save or are Done, owner decision 2026-10-10, S-27 A), waited for: leave() may return a promise, a question it asks is
// waited for as long as it is open, and only a Studio that stayed open keeps the second from opening
//   const M = hyModes({ dock, sel: () => [...ids], toast, t, rect: id => {x, y, w, h}, hy })   M.add(key, def)   M.sync()   M.enter(key, ids?)   M.el
(() => {
  if (window.hyModes) return;
  const EASE = "cubic-bezier(.32,.72,0,1)";
  // the board: the place where cards lie (ui/icons.js «board», the same as a board in Home's list)
  const BOARD_IC = () => (window.hyIcon ? window.hyIcon("board", 16) : "");
  // a thing's name as people read it: a file's name without its folder and its extension (sunset.png is «sunset»), else as given
  const FILE_EXT = /\.(png|jpe?g|webp|gif|heic|heif|tiff?|avif|bmp|psd|html?|json|glb|gltf|obj|fbx|stl|usdz|svg|pdf)$/i;
  const docName = s => String(s || "").trim().split("/").pop().replace(FILE_EXT, "").trim();
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
/* in any Studio the top row's right end is the Studio's own: its session actions (ui/hy/actions.js) stand at the window's edge, the
   board's round buttons and the panels they open are away until the board is back (owner 2026-10-09 on round 14's 3D Studio: «В режиме
   студии мы вот эти все элементы убираем»); <html data-in-studio> is set below for every Studio, a colourless plugin's too */
:root[data-in-studio] :is(#bntf, #bkeys, #bhist, #bset, #ntf, #hist, #keys, #sets.sw-side) { display: none !important; }
/* the board's Info card too, from the first moment (S-19, 2026-10-11: it showed through Image Studio for 2–3 s as its column came in) */
:root[data-in-studio] #info { display: none !important; }
#dock #modes > button[aria-disabled=true] { opacity: .38; cursor: default; }
#dock #modes > button[aria-disabled=true]:hover { color: var(--sub) !important; }
#dock #modes > button svg { flex: none; display: block; }
#dock #modes.few > button[aria-disabled=true], #dock #modes.solo > button:not([aria-pressed=true], [data-mode=board]) { display: none !important; }
:root[data-shape=pro] #dock #modes { border-radius: var(--hy-row-r, 8px) !important; }
:root[data-shape=pro] #dock #modes > :is(.st, button) { border-radius: calc(var(--hy-row-r, 8px) - var(--hy-seg-pad, 3px)) !important; }   /* concentric with the track */
/* the open thing's step in the crumb (the shell's doc()): a chevron and the name with the Studio's dot, grown in from the right */
#crumb .hycs, #cStudio { max-width: 0; opacity: 0; overflow: hidden; transition: max-width .4s ${EASE}, opacity .3s ${EASE}; }
#crumb .hycs.in { max-width: 16px; opacity: 1; } #cStudio.in { max-width: 260px; opacity: 1; }
#crumb #cStudio { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; color: var(--ink); cursor: default; }
#cStudio .hyd { width: 8px; height: 8px; border-radius: 99px; background: var(--hy-studio, var(--sel)); flex: none; }
#cStudio .hyn { overflow: hidden; text-overflow: ellipsis; }
#cStudio input { font: inherit; color: inherit; background: transparent; border: 0; outline: none; width: 160px; padding: 0; }
@media (prefers-reduced-motion: reduce) { #dock #modes > button { transition: none; } }`;
  window.hyModes = function ({ dock, sel, t = k => k, rect = null, hy = null }) {
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const LIFT = rect && window.hyEditLift ? window.hyEditLift({ rect }) : null;
    let liftK = "board", liftL = "board", entered = { k: "", id: null };
    const M = new Map([["board", { label: t("Board"), icon: BOARD_IC(), order: 0, title: t("Board: every card, the canvas itself"), board: true }]]);
    const wrap = document.createElement("div"), el = document.createElement("div");
    wrap.id = "modesw"; wrap.innerHTML = `<span class="msep" aria-hidden="true"></span>`;
    el.className = "seg"; el.id = "modes"; el.setAttribute("role", "group"); el.setAttribute("aria-label", t("Mode"));
    wrap.appendChild(el); dock.appendChild(wrap);
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
        // the app's tooltip (ui/hy/tooltip.js, round 20): the name, and in its quiet line what enables a disabled one
        b.hyTip = () => ({ t: b.dataset.name, sub: b.dataset.tip !== b.dataset.name ? b.dataset.tip : "" });
        if (d.color) b.style.setProperty("--hy-mode-c", d.color);   // the Studio's colour when chosen
      }
      if (window.hySeg) window.hySeg(el);
      sync(true); fit();
    }
    // what is chosen and what can be entered, from the open editor and the selection
    function sync(now) {
      if (!now) { if (!raf) raf = requestAnimationFrame(() => { raf = 0; sync(true); }); return; }
      const open = openKey(), ids = open === "board" ? safe(sel, []) : [cardOf(open, safe(sel, []))].filter(Boolean); let moved = false;   // in a Studio: its card
      for (const b of el.querySelectorAll(":scope > button")) {
        const k = b.dataset.mode, d = M.get(k); if (!d) continue;
        const on = k === open, can = d.board || on || !!safe(() => d.target && d.target(ids), null);
        if (b.getAttribute("aria-pressed") !== String(on)) b.setAttribute("aria-pressed", String(on));
        if (b.getAttribute("aria-disabled") !== String(!can)) { b.setAttribute("aria-disabled", String(!can)); moved = true; }
        // the tooltip: the name; on a disabled one also what enables it, in a Studio what to do instead (nothing can be selected there)
        const hint = can ? "" : ((open !== "board" && d.hintStudio) || d.hint || d.title || ""), desc = can ? (d.title || "") : hint;
        if (b.dataset.tip !== (hint || b.dataset.name)) b.dataset.tip = hint || b.dataset.name;
        if (desc) { if (b.getAttribute("aria-description") !== desc) b.setAttribute("aria-description", desc); } else b.removeAttribute("aria-description");
        if (window.hyTooltip) hyTooltip.refresh(b);
      }
      if ((moved && el.classList.contains("few")) || open !== fitFor) fit();
      paint(open);
      step(open);
      lift(open, ids);
    }
    // the open Studio's colour on <html> (data-studio, --hy-studio), gone on the board or in a Studio that brings none
    function paint(open) {
      const d = open !== "board" && M.get(open), c = d && d.color ? String(d.color) : "", r = document.documentElement;
      // any Studio, and a plugin's live view that holds the dock with its session actions top right (an HTML frame's live page, owner
      // 2026-10-11 on its Info card over the page: «пж убери в live preview вот это справа, это пиздец как мешает»): the row's right end
      // is its own, the board's Info card and round buttons are away until the board is back
      const live = !d && dock.classList.contains("plg-mode") && !!document.querySelector("body > hy-studio-actions");
      if (r.hasAttribute("data-in-studio") !== (!!d || live)) r.toggleAttribute("data-in-studio", !!d || live);
      if ((r.dataset.studio || "") === (c ? open : "") && r.style.getPropertyValue("--hy-studio") === c) return;
      if (c) { r.dataset.studio = open; r.style.setProperty("--hy-studio", c); } else { delete r.dataset.studio; r.style.removeProperty("--hy-studio"); }
    }
    // The open thing (doc()): its name for the crumb's step and the leave question, its path for the step's tooltip. The crumb gains the
    // step as a Studio opens and gives it back as it closes, the name follows a rename (studios audit S-06: Image Studio had a step, 3D
    // Studio a plate with the scene.json's path, Dev Studio nothing)
    function docOf(k) {
      const d = k && k !== "board" && M.get(k), x = d && d.doc ? safe(() => d.doc(), null) : null; if (!x) return null;
      const path = String(x.path || ""), name = docName(x.name || path); return name ? { name, path } : null;
    }
    let stepK = "";
    function step(open) {
      const cr = document.getElementById("crumb"), x = docOf(open);
      let st = document.getElementById("cStudio"), sp = document.getElementById("cStudioSep");
      if (!x || !cr) {
        if (st && stepK) { stepK = ""; st.classList.remove("in"); sp.classList.remove("in"); setTimeout(() => { if (!stepK) { st.remove(); sp.remove(); } }, 400); }
        return;
      }
      if (!st) {
        sp = document.createElement("span"); sp.className = "cs hycs"; sp.id = "cStudioSep"; sp.innerHTML = window.HY_CHEV || "›";
        st = document.createElement("button"); st.type = "button"; st.id = "cStudio"; st.innerHTML = `<i class="hyd"></i><span class="hyn"></span>`;
        st.addEventListener("click", e => { e.stopPropagation(); const d = M.get(stepK); if (d && d.docMenu && !st.querySelector("input")) safe(() => d.docMenu(st.getBoundingClientRect())); });
        st.addEventListener("dblclick", e => { e.stopPropagation(); renameStep(); });
        cr.append(sp, st);
      }
      if (st.nextElementSibling) cr.append(sp, st);   // the crumb's own parts drawn again after it: the step stays the last
      stepK = open;
      const n = st.querySelector(".hyn"); if (n && !st.querySelector("input") && n.textContent !== x.name) n.textContent = x.name;
      if (st.title !== x.path) st.title = x.path;
      st.setAttribute("aria-label", x.name);
      if (!st.classList.contains("in")) requestAnimationFrame(() => { if (stepK) { st.classList.add("in"); sp.classList.add("in"); } });
    }
    // a double click on the step: the name in a field where it stands (a name: ↵ and Tab apply, Esc puts it back, ⌘↵ the primary action)
    function renameStep() {
      const st = document.getElementById("cStudio"), d = M.get(stepK); if (!st || !d || !d.rename || st.querySelector("input")) return;
      const s = st.querySelector(".hyn"), old = s.textContent, inp = document.createElement("input");
      inp.value = old; inp.spellcheck = false; s.textContent = ""; s.appendChild(inp); inp.focus(); inp.select();
      let fin = false;
      const done = ok => { if (fin) return; fin = true; const v = inp.value.trim(); s.textContent = ok && v ? v : old; if (ok && v && v !== old) safe(() => d.rename(v)); sync(); };
      if (window.hyTyping && hyTyping.keys) hyTyping.keys(inp, { esc: "cancel", enter: "line", apply: () => done(true), cancel: () => done(false), primary: () => { done(true); safe(() => d.leave()); } });
      else inp.addEventListener("keydown", e => { e.stopPropagation(); if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); });
      inp.addEventListener("blur", () => done(true)); inp.addEventListener("click", e => e.stopPropagation());
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
      if (open !== liftK) { const was = liftK; liftK = open; if (was !== "board") depart(was); if (open !== "board") arrive(open, ids); }
      if (!LIFT) return;
      if (open !== liftL) { liftL = open; return LIFT.set(open === "board" ? null : cardOf(open, ids), open); }
      if (open === "board") return;
      const d = M.get(open), own = safe(() => d && d.card ? d.card() : null, null);
      if (own && own !== LIFT.id) LIFT.set(own, open); else if (!LIFT.id) LIFT.set(cardOf(open, ids), open); else LIFT.place();
    }
    // A Studio opens (P4 S-29, S-61): the Hint bar with every Studio's set, and the card flown between the Studio's panels, as Dev Studio
    // did alone before; it closes: the bar goes, the camera flies back to where the board was
    let hintH = null, camAt = null, flew = null, camKept = null;   // camKept: the board's camera while one Studio gives way to another
    function arrive(k, ids) {
      const d = M.get(k); if (!d) return;
      const items = hintItems(d);
      hintH = safe(() => d.showHint ? d.showHint(items, k) : window.hyKeyHint ? window.hyKeyHint.show(dock, k, items, { place: "top" }) : null, null);
      camAt = hy && d.fit !== false ? camKept || { ...hy.cam } : null; flew = null; camKept = null;
      if (!camAt) return;
      let n = 0;
      const go = () => {   // once the Studio's panels stand: two frames, and again while the free part is too small to measure
        if (openKey() !== k) return;
        if (d.fit) return safe(() => d.fit());
        const id = cardOf(k, ids), c = id && fitCam(id); if (!c) { if (++n < 12) requestAnimationFrame(go); return; }
        flew = id; fly(c);
      };
      requestAnimationFrame(() => requestAnimationFrame(go));
      // the library folds a moment after a Studio opens and its panels move with it: the card is fitted again once they settle (2 s)
      const t0 = performance.now(); let rt = 0;
      const mo = new MutationObserver(() => {
        if (performance.now() - t0 > 2000 || openKey() !== k || !flew) return;
        clearTimeout(rt); rt = setTimeout(() => { const c = flew && openKey() === k && fitCam(flew);
          if (c && (Math.abs(c.z - hy.cam.z) > .01 || Math.abs(c.x - hy.cam.x) * c.z > 4 || Math.abs(c.y - hy.cam.y) * c.z > 4)) fly(c, 300); }, 140);
      });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] }); setTimeout(() => mo.disconnect(), 2200);
    }
    // The Hint bar of a Studio, built here for all of them (S-04, 2026-10-11): V, C, one or two of its own keys, Esc / ⌘↵. A key held with
    // its modifiers is one combination, written as one cap without a slash: the slash means «or» (Esc / ⌘↵), and «⌥ / R» read as ⌥ or R
    const MODK = new Set(["alt", "option", "shift", "mod", "cmd", "meta", "ctrl", "control"]);
    const combo = keys => keys.length > 1 && keys.slice(0, -1).every(k => MODK.has(String(k).toLowerCase())) && !MODK.has(String(keys[keys.length - 1]).toLowerCase())
      ? [keys.join("+")] : keys;
    function hintItems(d) {
      return [{ id: "select", keys: ["v"], t: "Select" }, { id: "comment", keys: ["c"], t: "Annotation" },
        ...(d.hints || []).slice(0, 2).map(h => ({ ...h, keys: combo(h.keys || []) })), { id: "done", keys: ["escape", "mod+enter"], t: d.primary || "Done" }];
    }
    function depart() {
      if (hintH) { safe(() => hintH.hide()); hintH = null; }
      const it = flew && hy && hy.board.items[flew];
      if (waiting && waiting.to !== "board" && camAt) camKept = camAt;   // another Studio opens next: it flies from here, and back to the board's own camera at the end
      else if (it && camAt) fly({ ...camAt, cx: it.x + it.w / 2, cy: it.y + cardH(it) / 2 }, 380);
      flew = null; camAt = null;
    }
    // a card's height as the board draws it: a picture has no h, only its width and ratio (canvas.html itemH); without it the camera
    // flew to NaN and the whole board vanished after a Studio without its own camera opened on a picture (2026-10-10)
    const cardH = it => (typeof itemH === "function" ? itemH(it) : it.h) || it.h || it.w;
    // the camera that puts the card in the board's free part (ui/bars.js: the library, the Studio's side panels [data-hyui], the top row
    // and the dock), as large as fits, at most 4×
    function fitCam(id) {
      const it = hy.board.items[id], B = window.hyBars, st = hy.stage; if (!it || !B || !st) return null;
      const s = st.getBoundingClientRect(), f = B.free(st, parseFloat(document.documentElement.style.getPropertyValue("--inset")) || 0);
      const x0 = f.l + 16 - s.left, x1 = f.r - 16 - s.left, y0 = f.t + 8 - s.top, y1 = f.b - 8 - s.top;
      if (x1 - x0 < 80 || y1 - y0 < 80) return null;
      const h = cardH(it), z = Math.min((x1 - x0) / it.w, (y1 - y0) / h, 4); if (!(z > 0 && Number.isFinite(z))) return null;
      return { x: it.x - (x0 + (x1 - x0 - it.w * z) / 2) / z, y: it.y - (y0 + (y1 - y0 - h * z) / 2) / z, z, cx: it.x + it.w / 2, cy: it.y + h / 2 };
    }
    // the flight on the app's curve, cubic-bezier(.32,.72,0,1): the board point under the card's centre moves straight, the zoom evenly
    let flyRaf = 0;
    function bez(x) {
      const [a, b, c, d] = [.32, .72, 0, 1], X = s => 3 * a * s * (1 - s) ** 2 + 3 * c * s * s * (1 - s) + s ** 3, Y = s => 3 * b * s * (1 - s) ** 2 + 3 * d * s * s * (1 - s) + s ** 3;
      let lo = 0, hi = 1; for (let k = 0; k < 24; k++) { const m = (lo + hi) / 2; if (X(m) < x) lo = m; else hi = m; } return Y((lo + hi) / 2);
    }
    function fly(to, ms = 420) {
      cancelAnimationFrame(flyRaf);
      const from = { ...hy.cam }, t0 = performance.now(), still = matchMedia("(prefers-reduced-motion: reduce)").matches;
      const step = now => {
        const k = still ? 1 : Math.min(1, (now - t0) / ms), e = bez(k), z = from.z * (to.z / from.z) ** e;
        const sx = (to.cx - from.x) * from.z * (1 - e) + (to.cx - to.x) * to.z * e, sy = (to.cy - from.y) * from.z * (1 - e) + (to.cy - to.y) * to.z * e;
        hy.camera(to.cx - sx / z, to.cy - sy / z, z, k < 1);
        if (k < 1) flyRaf = requestAnimationFrame(step);
      };
      step(t0);
    }
    // a dock too narrow for all its buttons (a narrow window, the library open beside the board): the modes that cannot be entered now
    // step out (Board and the chosen one stay)
    // In a Studio only Board and that Studio (solo): the others cannot be entered from there anyway
    let fr = 0, fitFor = "";
    function fit(now) {
      if (!now) { if (!fr) fr = requestAnimationFrame(() => { fr = 0; fit(true); }); return; }
      fitFor = openKey(); el.classList.toggle("solo", fitFor !== "board");
      if (!dock.isConnected || !dock.offsetWidth) return;
      el.classList.remove("few");
      if (dock.scrollWidth > dock.clientWidth + 1) el.classList.add("few");
    }
    // enter mode k for these cards (the selection when not given), as its segment does; false when k is not there or takes none of them
    function enter(k, given) {
      const d = M.get(k), open = openKey(); if (!d || k === open) return false;
      const ids = given || safe(sel, []), id = d.board ? null : safe(() => d.target(ids), null);
      if (!d.board && !id) return false;
      waiting = null; entered = { k, id };
      const go = () => { if (!d.board) safe(() => d.enter(id)); sync(); };
      if (open === "board") { go(); return true; }
      // another Studio is open: it leaves its own way, keeping the work (it may ask, or still write), and this one opens once it is gone;
      // a Studio that stayed open (refused, or kept by the person) keeps it out (P4 S-31: a fixed 4 s gave up on a slow «Save»)
      if (d.board) { waiting = null; safe(() => M.get(open).leave()); sync(); return true; }   // the Board: its own leave, at once (it may still write)
      const ticket = waiting = { to: k };
      leaveFirst().then(ok => { const mine = waiting === ticket; waiting = null; if (ok && mine) go(); else { camKept = null; sync(); } });
      return true;
    }
    // the board around an open Studio: its own surface outside the card (#world: the cards, groups, arrows), not the card's handles
    const stage = document.getElementById("stage");
    const around = e => {
      const k = openKey(), w = document.getElementById("world"), x = e.target; if (k === "board" || !w || !x || !x.closest) return false;
      if (x !== stage && x !== w && !(w.contains(x) && !x.closest("#handles, #crop, #cmpins"))) return false;   // annotations' pins stay
      const id = cardOf(k, safe(sel, [])), c = id && document.querySelector(`#items > [data-id="${CSS.escape(id)}"]`);
      return !(c && c.contains(x));
    };
    for (const ev of ["pointerdown", "mousedown", "click", "dblclick", "contextmenu"]) {
      addEventListener(ev, e => { if (around(e)) { e.stopImmediatePropagation(); e.preventDefault(); } }, true);
    }
    let said = 0;
    const noDrop = e => {
      const k = openKey(); if (k === "board" || !stage || !stage.contains(e.target)) return;
      const d = M.get(k); if (d && d.drop && safe(() => d.drop(e), false)) return;
      e.stopImmediatePropagation(); e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "none";
      if (e.type !== "dragover" && Date.now() - said > 4000 && typeof window.toast === "function") {
        said = Date.now(); window.toast(t("{studio} is open: leave it to put this on the board", { studio: (d && (d.name || d.label)) || k }), "info");
      }
    };
    for (const ev of ["dragenter", "dragover", "drop"]) addEventListener(ev, noDrop, true);
    // leave the open Studio its own way and wait: true when the board is back, false when it stayed (it asked and the person kept it);
    // then the work a Studio still writes after leaving (pending): false when a write was refused, the page stays with it
    function leaveFirst() { return leaveOpen().then(ok => ok && settled()); }
    function settled() {
      const ps = defs().map(([, d]) => (d.pending ? safe(() => d.pending(), null) : null)).filter(p => p !== null && p !== undefined);
      return Promise.all(ps.map(p => Promise.resolve(p).catch(() => false))).then(r => r.every(x => x !== false));
    }
    function leaveOpen() {
      const k = openKey(); if (k === "board") return Promise.resolve(true);
      const p = safe(() => M.get(k).leave());   // a promise when the leave writes first (lesson 15): waited for
      const asking = () => [document, ...[...document.querySelectorAll("iframe")].map(f => { try { return f.contentDocument; } catch { return null; } })]
        .some(d => d && d.querySelector("#hyConfirm, [aria-modal=true], #dlgw.on"));
      return Promise.resolve(p).catch(() => {}).then(() => new Promise(ok => { let t0 = Date.now(); const poll = setInterval(() => {
        if (openKey() === "board") { clearInterval(poll); ok(true); }
        else if (asking()) t0 = Date.now();   // a question is open: the clock waits for the answer
        else if (Date.now() - t0 > 3000) { clearInterval(poll); ok(false); }
      }, 50); }));
    }
    // a browser asks before it unloads a page with a Studio's unsaved work (the board saves itself as it goes: no question for it). ⌘R is
    // never ours (owner 2026-10-10): in the app View › Reload Page has no key, so it does nothing; in a browser it reloads the tab, and
    // this question guards the work. A Studio's own reload is ⌥R (Dev Studio's page)
    addEventListener("beforeunload", e => { if (defs().some(([, d]) => d.unsaved && safe(() => d.unsaved(), false))) { e.preventDefault(); e.returnValue = ""; } });
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
    window.hyStudioDoc = () => docOf(openKey());   // for ui/confirm.js, also from a Studio's own page (parent.hyStudioDoc)
    build();
    return {
      el,
      add(key, def) { if (!key || key === "board" || !def) return; M.set(key, def); build(); },
      sync: () => sync(),
      // a mode entered by other means than its segment (a double click on a picture enters Image, owner 2026-10-07): true when it goes in
      enter: (k, ids) => enter(k, ids),
      leaveFirst,
      // the open Studio's card back between its panels, as when it opened (the view % in its dock, ui/boarddock.js); a Studio with its own
      // camera fits itself (fit()), one that keeps the camera (fit: false) is left as it is
      refit() {
        const k = openKey(), d = M.get(k); if (k === "board" || !d || d.fit === false || !hy) return false;
        if (d.fit) { safe(() => d.fit()); return true; }
        const id = cardOf(k, safe(sel, [])), c = id && fitCam(id); if (!c) return false;
        flew = id; fly(c, 380); return true;
      },
      // the Studio one selected card opens on the board, for the chip over it (ui/studiochip.js, owner 2026-10-10 round 19 switch-d): {key,
      // name, color} of the first mode whose target is that card, the order the switch shows them; null for none, several or a Studio open
      studioFor(ids) {
        if (openKey() !== "board" || !ids || ids.length !== 1) return null;
        for (const [k, d] of defs()) if (!d.board && safe(() => d.target && d.target(ids), null) === ids[0]) return { key: k, name: d.name || d.label || k, color: d.color ? String(d.color) : "" };
        return null;
      },
      get open() { return openKey(); },
      // the open Studio's thing, { name, path }, or null on the board: the crumb's step and the leave question (ui/confirm.js) say this name
      doc: () => docOf(openKey()),
      get hint() { return hintH; },   // the open Studio's Hint bar: used(id) when a key's action came by the mouse
    };
  };
})();
