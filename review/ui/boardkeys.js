// The board's keys (canvas.html, moved here 2026-10-10 so the page gets smaller, docs/process.md П4): one listener on the window for every
// plain key of the board and its ⌘ commands. canvas.html calls hyBoardKeys.listen() where the listener stood, so it keeps its place among
// the page's other listeners. Every branch names its keys in a «// key:» comment, as the «?» panel (canvas.html #keys) writes them; a test
// checks that each has a row there and no key has two (tests/test_p4_medium.py, P4 B-39).
(() => {
  if (window.hyBoardKeys) return;
  function onKey(e) {
    // a field you type into takes every key, a control with the focus only its own (ui/typing.js; P4 S-15: a checkbox took them all)
    if (hyTyping(e) || hyTyping.ownKey(e)) return;
    for (const P of Object.values(PLG)) if (P.onKey && P.onKey(e)) return;   // a plugin card in use takes its keys first (Esc, Delete)
    const k = e.key, mod = e.metaKey || e.ctrlKey;
    if (k === " ") { if (!e.repeat && !SPACE) SPACE = { t: performance.now(), used: !!drag }; space = true; stage.classList.add("space"); e.preventDefault(); return; }   // key: Space
    if (MODES && MODES.open !== "board" && k !== "\\") return;   // a Studio is open: the board's keys wait, the app's (⌘. ⌘M ⌘K, \\) stay (P4 S-06)
    if (cropState) {   // key: ↵ Esc R X ⌘Z (in a crop)
      const u = cropState.undo, keep = () => u.push([...cropState.c]);
      if (k === "Enter") applyCrop(); else if (k === "Escape") endCrop();
      else if (mod && (k === "z" || k === "я")) { e.preventDefault(); if (u.length) { cropState.c = u.pop(); drawCrop(); } }   // ⌘Z: the crop's last change back (P4 B-46)
      else if (k === "r" || k === "R" || k === "к" || k === "К") { keep(); cropReset(); }
      else if (!mod && (e.code === "KeyX" || ["x", "ч"].includes(k.toLowerCase()))) { keep(); cropRatio("flip"); }
      return;
    }
    if (mod && (k === "z" || k === "я")) { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }   // key: ⌘Z ⇧⌘Z
    if (mod && (k === "d" || k === "в")) { e.preventDefault(); duplicate(); return; }   // key: ⌘D
    // two keys right above ⌥, one hand (owner 2026-09-29): ⌥A square block, ⌥S one row; ⌥ turns the letter into å/ß on a Mac, so the physical key is checked too
    if (e.altKey && !mod && (e.code === "KeyA" || ["a", "ф", "å"].includes(k.toLowerCase()))) { e.preventDefault(); tidy(); return; }   // key: ⌥A
    if (e.altKey && !mod && (e.code === "KeyS" || ["s", "ы", "ß"].includes(k.toLowerCase()))) { e.preventDefault(); tidyRow(); return; }   // key: ⌥S
    if (e.altKey && !mod && (e.code === "KeyP" || ["p", "з", "π"].includes(k.toLowerCase()))) { e.preventDefault(); splitPdfSel(); return; }   // key: ⌥P
    if (e.altKey && !mod && (e.code === "KeyD" || ["d", "в", "∂"].includes(k.toLowerCase()))) { e.preventDefault(); smartTidy(); return; }   // key: ⌥D
    // by physical key when the browser reports it, else by the letter in either layout
    const is = (code, ...ks) => e.code === code || ks.includes(k.toLowerCase());
    if (mod && e.shiftKey && is("KeyC", "c", "с")) { e.preventDefault(); hyCopyImage.key([...sel]); return; }   // key: ⇧⌘C, Figma's «Copy as PNG» (ui/copyimage.js)
    if (mod && is("KeyC", "c", "с")) { e.preventDefault(); copySel(); return; }   // key: ⌘C
    const paused = () => { if (!pausedSel()) return false; toast(T("The group is bigger than the screen, its selection is paused. Zoom out to delete or cut it")); return true; };
    if (mod && is("KeyX", "x", "ч")) { e.preventDefault(); if (!paused()) cutSel(); return; }   // key: ⌘X
    if (mod && is("KeyV", "v", "м")) { pasteKey(); return; }   // key: ⌘V; no preventDefault: the browser's paste event brings the clipboard picture
    // like Figma (owner 2026-09-29): ⌘G groups, ⇧⌘G ungroups; the browser's own ⌘G (find next) is blocked here
    if (mod && (e.code === "KeyG" || k === "g" || k === "G" || k === "п" || k === "П")) { e.preventDefault(); e.shiftKey ? ungroup() : makeGroup(); return; }   // key: ⌘G ⇧⌘G
    // the order, as in Figma (owner 2026-10-06): ⌘] ⌘[ one step, with ⌥ to the very top or bottom; by the physical key (⌥ changes the letter,
    // the Russian layout has х ъ there); the browser's own ⌘[ ⌘] (back, forward) never runs on the board
    if (mod && !e.shiftKey && (e.code === "BracketRight" || e.code === "BracketLeft")) {   // key: ⌘] ⌘[ ⌥⌘] ⌥⌘[
      e.preventDefault(); orderMove(e.code === "BracketRight" ? (e.altKey ? "front" : "forward") : (e.altKey ? "back" : "backward")); return;
    }
    // ⌘A: the groups no group holds and every card outside them (P4 B-21: the cards without their groups left empty frames on ⌫ and a drag)
    if (mod && (k === "a" || k === "ф")) { e.preventDefault(); sel = new Set(hySel.tops()); selArrow = null; render(); return; }   // key: ⌘A
    if (mod) return;
    if (/^Arrow(Left|Right|Up|Down)$/.test(k) && !e.altKey) { if (nudgeOk()) { e.preventDefault(); nudge(k, e.shiftKey); } return; }   // key: ←↑→↓ a screen pixel (⇧ ten)
    if (k === "g" || k === "G" || k === "п" || k === "П") { e.preventDefault(); e.shiftKey ? ungroup() : makeGroup(); }   // key: G ⇧G; the g is not typed into the new name
    else if (e.shiftKey && is("KeyC", "c", "с")) startCropSel();   // key: ⇧C; C alone starts an annotation (ui/anncore.js)
    else if (k === "Backspace" || k === "Delete") {   // key: ⌫
      const tli = tlSel && board.items[tlSel.id], q = tli && tli.points.find(x => x.id === tlSel.pid);
      if (q && q.t !== 0) { const before = snap(); tli.points = tli.points.filter(x => x !== q); tlSel = null; hySel.deleted(before, [], [], T("a dot")); }   // a dot, not the line
      else if (selArrow) removeArrow(); else if (!paused()) removeSel();
    }
    else if (/^Digit[0-9]$/.test(e.code) && !e.shiftKey && !e.altKey && hySel.pick(sel).some(id => opOk(board.items[id]))) {   // key: 1 0; 1…9 = 10…90 %, 0 = 100 %, as in Figma
      e.preventDefault(); const d = +e.code.slice(5); setOpacity(d === 0 ? 1 : d / 10, false);
    }
    else if (is("KeyL", "l", "д")) { e.preventDefault(); newTimeline(true); }   // key: L
    else if (is("KeyF", "f", "а")) {   // key: F, ♥ on the selected
      if (e.repeat) { e.preventDefault(); return; } const ids = hySel.pick(sel).filter(id => hyCardFav.path(board.items[id])); e.preventDefault();
      if (ids.length) toggleFav(ids); else if (sel.size) hyWhy(T("♥ is for pictures and pages"));   // a group's pictures too (P4 B-23), a note says why (B-48)
    }
    else if (is("KeyN", "n", "т")) { e.preventDefault(); newNote(true); }   // key: N; the note's field takes focus right away: without this the "n" itself was typed into it (owner 2026-10-01)
    else if (k === "Escape") { sel.clear(); tlSel = null; selArrow = null; render(); }   // key: Esc, the last: the selection, a selected arrow too (P4 B-20)
    else if (k === "Enter" && !e.shiftKey && !e.altKey && sel.size === 1 && hyInfoHead.open()) e.preventDefault();   // key: ↵ the Info header's Open (P4 B-36)
    else if (k === "!" || (e.shiftKey && e.code === "Digit1")) fit();   // key: ⇧1
    else if (k === "\\") EMBED ? parent.postMessage({ type: "toggleCanvasFull" }, location.origin) : toggleLib();   // key: \ in the app ⌘M's, never the old library (P4 B-13)
  }
  // One order for Esc on the board (P4 B-16, B-17, B-44): a drag, a resize or a selection frame in progress stops and everything goes back
  // to where it began; then the open thread of an annotation (its mention list first), the page's annotations, a version being looked at,
  // History, Notifications, the «?» panel, the pages menu; then the Annotation tool (ui/anncore.js); the selected arrow and the selection
  // last (onKey). A search with words in it clears them first (its own field). Not while you type, under a viewer, in a Studio or a crop:
  // those have their own Esc. On the window before anything else, so a panel closes before the selection goes.
  const open = q => { const el = $(q); return !!el && (el.classList.contains("open") || el.style.display === "block"); };
  function cancelDrag() {
    const d = drag; if (!d || d.mode === "scrub") return false;
    drag = null; if (moveRaf) { cancelAnimationFrame(moveRaf); moveRaf = 0; moveEv = null; }
    if (d.before && d.mode !== "marq" && d.mode !== "pan") {
      const o = JSON.parse(d.before); board.items = o.items; board.groups = o.groups; board.grids = o.grids; board.links = o.links; board.removed = o.removed || {};
      sel = new Set((o.sel || []).filter(id => board.items[id] || board.groups[id]));
    }
    if (d.mode === "marq") sel = new Set(d.was || d.base);
    stage.classList.remove("panning"); $("#marq").style.display = "none";
    document.querySelectorAll(".grp.drop, .linktarget").forEach(el => { el.classList.remove("drop", "linktarget"); el.style.removeProperty("--lt"); });
    if (d.kh && d.kh.hide) d.kh.hide(); if (window.hySnap) hySnap.clear();
    render(); renderHandles(); renderLinks(); return true;
  }
  function onEsc(e) {
    if (e.key !== "Escape" || hyTyping(e) || hyTyping.ownKey(e) || typeof board === "undefined") return;
    if ((typeof VBIG !== "undefined" && VBIG) || (MODES && MODES.open !== "board") || $("#ctx.open") || document.querySelector("#hyConfirm, #propsDlg")) return;
    const take = fn => { e.preventDefault(); e.stopImmediatePropagation(); fn(); };
    if (drag) { if (cancelDrag()) take(() => {}); return; }
    if (window.hyConn && hyConn.cancelPull && hyConn.cancelPull()) return take(() => {});
    if (cropState) return;   // the crop's own Esc (onKey)
    const C = window.hyComments;
    if (C && C.escape()) return take(() => {});   // the mention list, then the open thread: its words stay as a draft (ui/comments.js)
    if (open("#cmlist")) return take(() => $("#cmlist").classList.remove("open"));
    if (PREV) return take(exitPreview);
    for (const q of ["#hist", "#ntf", "#keys"]) if (open(q)) return take(() => { closeSide(); side(); });
    if (open("#pages")) return take(closePages);
  }
  addEventListener("keydown", onEsc, true);
  // a version being looked at takes no new work: N, L, a double click, ⌘V and a drop say so before anything opens (P4 B-28: a whole note
  // was typed and then rolled back)
  window.hyPrevNo = () => {
    if (typeof PREV === "undefined" || !PREV) return false;
    toast(T("This is a version preview. To change it, press “Restore this version”"), "info", { key: "why" }); return true;
  };
  window.hyBoardKeys = { listen: () => addEventListener("keydown", onKey), onKey, cancelDrag };
})();
