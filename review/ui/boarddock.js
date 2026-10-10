// The board's dock (owner 2026-10-10 on round 18, r18-dock.html, ★ yes), on ui/dock.js: create | tools | Undo, Redo | view % and the
// save status | the switch of Studios.
//   create   one «+» that opens the list of what can be made here (owner on the old row of buttons: «Вот эта иконка мне вообще не нравится»
//            of the timeline, and the board's create buttons under one «+» as 3D Studio's «+» Add): Note N, Text, Timeline L, then what
//            the plugins add (HY.addButton: 3D scene). The timeline wears the icon of a line with its phases (ui/icons.js layoutTimeline)
//   tools    #dtools: Annotation (ui/anncore.js puts its button there)
//   history  Undo and Redo, the step's name on a plate over them under the pointer and for 2 s after ⌘Z or ⇧⌘Z (ui/dock.js steps). The
//            board keeps its steps as JSON strings (canvas.html past and future), so the name is what changed between two of them:
//            «Move», «New note», «Grouped 3», «Deleted: 2»; a step outside the snapshot (♥, a page's name) says its own (ui/undofx.js)
//   view %   the zoom's percent is a button now, a click shows all (⇧1), as the separate «Show all» did. While a Studio is open it stands
//            in that Studio's dock where the Studio leaves it a place (<span data-dk="view">) and a click flies its card back between
//            the Studio's panels (ui/modes.js refit); 3D Studio and Dev Studio show it, Image Studio has its own zoom
//   hyBoardDock.add(svg, title, fn, o)   an item of «+» (HY.addButton); o.label its words in the list, else the title up to «:»
//   hyBoardDock.dock(node)               HY.dock: the view % goes into a Studio's dock and comes back home
(() => {
  if (window.hyBoardDock) return;
  const $ = q => document.querySelector(q);
  const ic = (n, s = 16) => (window.hyIcon ? window.hyIcon(n, s, 1.85) : "");
  const EXTRA = [];   // the plugins' items of «+»
  let PLUS = null, STEPS = null;
  function items() {
    const it = (attrs, icon, label, keys) => window.hyMenuItem(attrs, icon, T(label), keys);
    return it('data-mk="note"', ic("note"), "Sticky note", ["N"]) + it('data-mk="text"', ic("drawText"), "Text")
      + it('data-mk="timeline"', ic("layoutTimeline"), "Timeline", ["L"])
      + EXTRA.map((x, i) => window.hyMenuItem(`data-mk="x${i}" title="${String(x.title).replace(/"/g, "&quot;")}"`, x.svg, x.label)).join("");
  }
  function make(k) {
    if (k === "note") return newNote(false);
    if (k === "timeline") return newTimeline(false);
    if (k === "text") return window.hyTextDoc && hyTextDoc.create();
    const x = EXTRA[+String(k).slice(1)]; if (x && x.fn) x.fn();
  }
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
    if (ch.length || gch.length) {
      const keys = new Set(); for (const k of ch) for (const f of new Set([...Object.keys(ia[k]), ...Object.keys(ib[k])])) if (!same(ia[k][f], ib[k][f])) keys.add(f);
      for (const k of gch) for (const f of new Set([...Object.keys(ga[k]), ...Object.keys(gb[k])])) if (!same(ga[k][f], gb[k][f])) keys.add(f === "title" ? "text" : f);
      const kinds = FIELDS.filter(([, fs]) => fs.some(f => keys.has(f))).map(([k]) => k), n = ch.length + gch.length;
      const k = kinds.includes("text") ? "text" : kinds.includes("size") ? "size" : kinds[0];
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
    if (dir === "undo") return past.length ? named(past[past.length - 1], snap()) : "";
    return future.length ? named(snap(), future[future.length - 1]) : "";
  }
  // ---- the view % in a Studio's dock -----------------------------------------------------------------------------------------------
  function dock(node) {
    const f = $("#bfit"), home = $("#status"); if (!f || !home) return;
    const ph = node && node.querySelector("[data-dk=view]");
    if (ph) { ph.appendChild(f); f.title = T("Fit the card between the panels"); f.setAttribute("aria-label", T("Fit the card between the panels")); }
    else if (f.nextElementSibling !== home) { home.before(f); f.title = T("Show all · ⇧1"); f.setAttribute("aria-label", T("Show all")); }
  }
  function init() {
    const btn = $("#bplus"), dk = $("#dock"); if (!btn || !dk || !window.hyDock || !window.hyMenuItem) return void setTimeout(init, 50);
    const el = document.createElement("div"); el.id = "bplusm"; el.setAttribute("aria-label", T("Create"));
    PLUS = hyDock.menu(btn, el, { fill: m => { m.innerHTML = items(); }, pick: b => make(b.dataset.mk) });
    STEPS = hyDock.steps({ undo: $("#bundo"), redo: $("#bredo"), name: stepName });
    if (typeof HY !== "undefined" && HY.restored) HY.restored(why => { if (why === "undo" || why === "redo") STEPS.done(why); });
    // in a Studio the percent fits that Studio's card, not the whole board
    $("#bfit").addEventListener("click", e => {
      if (typeof MODES === "undefined" || !MODES || MODES.open === "board") return;
      e.stopImmediatePropagation(); e.preventDefault(); MODES.refit();
    }, true);
  }
  window.hyBoardDock = {
    add(svg, title, fn, o = {}) { const x = { svg, title, fn, label: o.label || String(title).split(/[:·]/)[0].trim() }; EXTRA.push(x); return x; },
    dock, stepName, named,
    get menu() { return PLUS; }, get steps() { return STEPS; },
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", init); else init();
})();
