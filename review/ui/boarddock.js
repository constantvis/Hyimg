// The board's dock (owner 2026-10-10 on round 18, r18-dock.html, ★ yes), on ui/dock.js: create | tools | Undo, Redo | view % and the
// save status | the switch of Studios.
//   create   one «+» that opens the list of what can be made here (owner on the old row of buttons: «Вот эта иконка мне вообще не нравится»
//            of the timeline, and the board's create buttons under one «+» as 3D Studio's «+» Add): Note N, Text, Timeline L, then what
//            the plugins add (HY.addButton: 3D scene). The timeline wears its one icon, two dots, a line, an arrow (ui/icons.js timeline,
//            round 21: the «?» panel shows the same)
//   tools    #dtools: Annotation (ui/anncore.js puts its button there)
//   history  Undo and Redo, the step's name on a plate over them under the pointer and for 2 s after ⌘Z or ⇧⌘Z (ui/dock.js steps). The
//            board keeps its steps as JSON strings (canvas.html past and future), so the name is what changed between two of them:
//            «Move», «New note», «Grouped 3», «Deleted: 2»; a step outside the snapshot (♥, a page's name) says its own (ui/undofx.js),
//            a step named by its command says that («Arrange as a grid»), and its pictures follow as tiles (round 21, stepThings)
//   view %   the zoom's percent is a button, a click opens the zoom's menu (ui/boardzoom.js, round 20; before, a click showed all). In a Studio it stands
//            in that Studio's dock where the Studio leaves it a place (<span data-dk="view">) and a click flies its card back between
//            the Studio's panels (ui/modes.js refit); 3D Studio and Dev Studio show it, Image Studio has its own zoom
//   hyBoardDock.add(svg, title, fn, o)   an item of «+» (HY.addButton); o.label its words in the list, else the title up to «:»
//   hyBoardDock.dock(node)               HY.dock: the view % goes into a Studio's dock and comes back home
//   hyBoardDock.list(size), make(k, at)  what «+» makes, also the empty board's right click (round 20, board audit B-18): at the click
// Every icon of «+» is 16 px, a plugin's too (board audit B-22: 3D Studio's was 18 and moved its words 2 px)
(() => {
  if (window.hyBoardDock) return;
  const $ = q => document.querySelector(q);
  const ic = (n, s = 16) => (window.hyIcon ? window.hyIcon(n, s, 1.85) : "");
  const EXTRA = [];   // the plugins' items of «+»
  let PLUS = null, STEPS = null;
  const list = (s = 16) => [{ k: "note", icon: ic("note", s), label: T("Sticky note"), keys: ["N"] }, { k: "text", icon: ic("drawText", s), label: T("Text"), keys: ["T"] },
    { k: "timeline", icon: ic("timeline", s), label: T("Timeline"), keys: ["L"] }, ...EXTRA.map((x, i) => ({ k: "x" + i, icon: x.svg, label: x.label, title: x.title }))];
  const items = () => list().map(x => window.hyMenuItem(`data-mk="${x.k}"${x.title ? ` title="${String(x.title).replace(/"/g, "&quot;")}"` : ""}`, x.icon, x.label, x.keys)).join("");
  // at: a point on the board (the right click's), else where the dock makes things (the middle of the free board)
  function make(k, at) {
    if (at && typeof lastPt !== "undefined") lastPt = at;
    if (k === "note") return newNote(!!at);
    if (k === "timeline") return newTimeline(!!at);
    if (k === "text") return window.hyTextDoc && hyTextDoc.create(at || undefined);
    const x = EXTRA[+String(k).slice(1)]; if (x && x.fn) x.fn();
  }
  const st = document.createElement("style"); st.textContent = "#bplusm [role=menuitem] > svg { width: 16px; height: 16px; flex: none; }";
  (document.head || document.documentElement).appendChild(st);
  // ---- the step's name: what changed between two of the board's strings ---------------------------------------------------------
  const NEW = { note: "step::New note", text: "step::New text", timeline: "step::New timeline" };
  const FIELDS = [["text", ["text", "label", "points", "title", "body"]], ["move", ["x", "y"]], ["size", ["w", "h", "fs", "size", "len", "tw", "dir"]],
    ["colour", ["color"]], ["crop", ["crop", "trim"]], ["opacity", ["op", "opacity"]], ["fav", ["fav", "rate"]], ["arrow", ["to", "reach"]]];
  const WORD = { text: "step::Text", move: "step::Move", size: "step::Size", colour: "step::Colour", crop: "step::Crop", opacity: "step::Opacity", fav: "♥", arrow: "step::Arrow" };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function named(sa, sb) {
    const fx = window.hyUndoFx && hyUndoFx.label ? hyUndoFx.label(sa) || hyUndoFx.label(sb) : ""; if (fx) return fx;
    let A, B; try { A = JSON.parse(sa); B = JSON.parse(sb); } catch { return ""; }
    const ia = A.items || {}, ib = B.items || {}, ga = A.groups || {}, gb = B.groups || {};
    const add = Object.keys(ib).filter(k => !ia[k]), gone = Object.keys(ia).filter(k => !ib[k]);
    const gAdd = Object.keys(gb).filter(k => !ga[k]), gGone = Object.keys(ga).filter(k => !gb[k]);
    if (gAdd.length && !add.length && !gone.length) return T("step::Grouped {n}", { n: (gb[gAdd[0]].members || []).length });
    if (gGone.length && !add.length && !gone.length) return T("step::Ungrouped");
    if (add.length && !gone.length) return add.length === 1 ? T(NEW[ib[add[0]].type] || "step::New card") : T("step::Added: {n}", { n: add.length });
    if (gone.length + gGone.length && !add.length) return T("step::Deleted: {n}", { n: gone.length || gGone.length });
    const ch = Object.keys(ib).filter(k => ia[k] && !same(ia[k], ib[k])), gch = Object.keys(gb).filter(k => ga[k] && !same(ga[k], gb[k]));
    const tb = ch.length === 1 && !gch.length && window.hyTextBox ? hyTextBox.stepName(ia[ch[0]], ib[ch[0]]) : ""; if (tb) return tb;   // a text's box
    if (ch.length || gch.length) {
      const keys = new Set(); for (const k of ch) for (const f of new Set([...Object.keys(ia[k]), ...Object.keys(ib[k])])) if (!same(ia[k][f], ib[k][f])) keys.add(f);
      for (const k of gch) for (const f of new Set([...Object.keys(ga[k]), ...Object.keys(gb[k])])) if (!same(ga[k][f], gb[k][f])) keys.add(f === "title" ? "text" : f);
      const kinds = FIELDS.filter(([, fs]) => fs.some(f => keys.has(f))).map(([k]) => k), n = ch.length + gch.length;
      const k = kinds.includes("text") ? "text" : kinds.includes("crop") ? "crop" : kinds.includes("size") ? "size" : kinds[0];   // a crop moves and sizes too (B-12)
      if (k === "move") return n > 1 ? T("step::Move {n}", { n }) : T(WORD.move);
      if (k) return T(WORD[k]);
    }
    if (!same(A.links, B.links)) return T("step::Arrow");
    if (!same(A.grids, B.grids)) return T("step::Arrange");
    return T("step::Change");
  }
  // the step Undo would take is the newest of past, against the board now; Redo's the newest of future against the board now
  function stepName(dir) {
    if (typeof past === "undefined") return "";
    if (typeof cropState !== "undefined" && cropState) return (dir === "undo" ? cropState.undo : cropState.redo).length ? T("step::Crop frame") : "";   // B-06
    if (dir === "undo") return past.length ? named(past[past.length - 1], snap()) : "";
    return future.length ? named(snap(), future[future.length - 1]) : "";
  }
  // the step's pictures for the plate over Undo and Redo (round 21: «Имя шага над Undo с вещами»), the same tiles as its note
  function stepThings(dir) {
    if (typeof past === "undefined" || !window.hyUndoFx || (typeof cropState !== "undefined" && cropState)) return null;
    if (dir === "undo") return past.length ? hyUndoFx.things(past[past.length - 1], snap()) : null;
    return future.length ? hyUndoFx.things(snap(), future[future.length - 1]) : null;
  }
  // ---- the view % in a Studio's dock -----------------------------------------------------------------------------------------------
  function dock(node) {
    const f = $("#bfit"), home = $("#status"); if (!f || !home) return;
    const ph = node && node.querySelector("[data-dk=view]");
    if (ph) { ph.appendChild(f); f.title = T("Fit the card between the panels"); f.setAttribute("aria-label", T("Fit the card between the panels")); }
    else if (f.nextElementSibling !== home) { home.before(f); f.title = T("View zoom"); f.setAttribute("aria-label", T("View zoom")); }   // its menu (ui/boardzoom.js)
  }
  function init() {
    const btn = $("#bplus"), dk = $("#dock"); if (!btn || !dk || !window.hyDock || !window.hyMenuItem) return void setTimeout(init, 50);
    const el = document.createElement("div"); el.id = "bplusm"; el.setAttribute("aria-label", T("Create"));
    PLUS = hyDock.menu(btn, el, { fill: m => { m.innerHTML = items(); }, pick: b => make(b.dataset.mk) });
    STEPS = hyDock.steps({ undo: $("#bundo"), redo: $("#bredo"), name: stepName, things: stepThings });
    if (typeof HY !== "undefined" && HY.restored) HY.restored(why => { if (why === "undo" || why === "redo") STEPS.done(why); });
    // in a Studio the percent fits that Studio's card, not the whole board
    $("#bfit").addEventListener("click", e => {
      if (typeof MODES === "undefined" || !MODES || MODES.open === "board") return;
      e.stopImmediatePropagation(); e.preventDefault(); MODES.refit();
    }, true);
  }
  window.hyBoardDock = {
    add(svg, title, fn, o = {}) { const x = { svg, title, fn, label: o.label || String(title).split(/[:·]/)[0].trim() }; EXTRA.push(x); return x; },
    dock, stepName, named, list, make,
    get menu() { return PLUS; }, get steps() { return STEPS; },
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", init); else init();
})();
