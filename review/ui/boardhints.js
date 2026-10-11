// The board's key hints and tips (ui/hy/keyhint.js and ui/hy/tip.js, owner 2026-10-08: «Shift+Enter — готово ... такого рода подсказки я бы
// еще сделал много где»): each context of the board and the keys it really has, read from canvas.html and ui/comments.js. A key that does
// not exist is not here. The studios and the shared slider hold their own (hyimg-image-studio, hyimg-3d-studio, hyimg-dev-studio, ui/slider.js).
//   const h = hyHint("note", el)              shows the note's keys on it; h.hide() when the context ends, h.used("list")
//   hyHint("move", el, { untilUp: true })     a drag's: gone with the pointer's release
//   hyHint("ann:arrow", bar)                  a mode's tool, in the Hint bar: «ann» is what learns, so Esc used with the pen counts for the arrow
// Owner 2026-10-09 on round 12 «Key hints on the surface»: what is written on a surface (a note, a heading, a field) is the ↵ alone, bare,
// in its ink, no word, no plate («просто Enter символа достаточно, писать Send не нужно, а Line убери»; «даже без подложки»); the glass
// capsule with words stays for a drag and a resize («да, отличные вот эти») and the Hint bar at the top.
(() => {
  if (window.hyHint) return;
  // ↵ finishes (Esc and ⌘↵ too, counted, not shown); ⇧↵, a new line where there is one, is not shown either
  const enter = (also = ["escape", "mod+enter"]) => [{ id: "done", keys: ["enter"], t: "", also }], leave = { id: "done", keys: ["escape"], t: "Done" };
  const H = window.HY_BOARD_HINTS = {
    // canvas.html editNote: always there on the note's paper at its corner (owner 2026-10-08: «без темного фона», «ничего другого не нужно»;
    // 2026-10-09: «the apply button from cmd+enter to just enter»)
    note: [{ ...enter()[0], stay: true }],
    heading: enter(["escape"]),   // editText; a group's title (renameGroup) and a timeline's label (editTlLabel) alike
    rename: enter(["escape"]),    // a page (renamePage), a group's title stuck at the top (renamePlate)
    board: enter([]),             // the board's name (renameBoard): Esc cancels there, so it does not count as finishing
    comment: enter([]),           // ui/comments.js key(): ↵ sends, ⇧↵ a new line, @ mentions; only the ↵ is shown (owner: «Line убери»)
    move: [{ id: "axis", keys: ["shift"], t: "One axis" }],   // ⌥ copies only when held before the drag starts: not shown mid-drag
    resize: [{ id: "centre", keys: ["alt"], t: "From the centre" }],   // one thing: pictures always keep their ratio, ⇧ does nothing
    mresize: [{ id: "ratio", keys: ["shift"], t: "Keep proportions" }, { id: "centre", keys: ["alt"], t: "From the centre" }],   // ui/multiscale.js
    // ui/annotate.js, a tool of the dock: ⇧ while drawing (constrain), ⇧-click and ⌫ with Select; Esc steps out, last of all the mode
    "ann:comment": [leave], "ann:pen": [leave], "ann:text": [leave], "ann:eraser": [leave],
    "ann:arrow": [{ id: "snap", keys: ["shift"], t: "45°" }, leave], "ann:rect": [{ id: "square", keys: ["shift"], t: "Square" }, leave],
    "ann:ellipse": [{ id: "circle", keys: ["shift"], t: "Circle" }, leave],
    // the crop (ui/cropframe.js) in the Hint bar (round 20, tips-a.html, board audit B-19): X turns the ratio, ↵ applies, Esc cancels;
    // a video's crop and trim has no ratio key; «crop:trim» learns with «crop»
    crop: [{ id: "ratio", keys: ["x"], t: "Ratio" }, { id: "apply", keys: ["enter"], t: "Apply" }, { id: "cancel", keys: ["escape"], t: "Cancel" }],
    "crop:trim": [{ id: "apply", keys: ["enter"], t: "Apply" }, { id: "cancel", keys: ["escape"], t: "Cancel" }],
    "ann:select": [{ id: "add", keys: ["shift"], t: "Add to selection" }, { id: "del", keys: ["backspace"], t: "Delete" }, leave],
  };
  // where: on the thing (a note's corner; a field's end, or right after a field as wide as its words), in glass under a drag, in the bar
  const PLACE = { note: { bare: true }, heading: { place: "end", bare: true }, rename: { place: "end", bare: true },
    board: { place: "end", bare: true, after: false }, comment: { place: "end", bare: true, after: false },
    move: { place: "below" }, resize: { place: "below" }, mresize: { place: "below" }, ann: { place: "top" }, crop: { place: "top" } };
  const NOOP = { hide() {}, used() {}, key() {} };
  window.hyHint = (ctx, anchor, opts = {}) => {
    const K = window.hyKeyHint; if (!K || !anchor || !(opts.items || H[ctx])) return NOOP;
    const how = { ...(PLACE[ctx] || PLACE[ctx.split(":")[0]] || {}), ...opts };
    const h = K.show(anchor, ctx.split(":")[0], opts.items || H[ctx], how);   // «ann:arrow»: the tools of one mode learn together
    if (opts.untilUp) addEventListener("pointerup", () => h.hide(), { capture: true, once: true });
    return h;
  };

  // The tip of an empty page (ui/hy/tip.js, round 12's version 9, owner 2026-10-09: «9 версия идеальна — делай»): under «Drag frames from
  // the library on the left», one tip each time an empty page shows, a click for the next. Only what the board really does.
  const TIPS = [
    { id: "note", t: "<b>N</b> puts a note here", keys: ["n"] },   // canvas.html, KeyN: newNote
    { id: "paste", t: "<b>⌘V</b> pastes a picture", keys: ["mod+v"] },   // canvas.html, the paste listener
    { id: "folder", t: "<b>Drag a folder</b> from the library: it lands as a block", auto: false },   // v2.html, a folder row is draggable
  ];
  let tip = null, shown = false, wait = 0;
  const watch = () => {
    const E = document.getElementById("empty"); if (!E) return;
    let host = null;
    const sync = () => {
      const on = getComputedStyle(E).display !== "none" && !!window.hyTip;
      if (on === shown) return; shown = on;
      if (tip) { tip.hide(); tip = null; }
      if (!on) return;
      if (!host) {   // under the line, centred as it is (#empty's padding keeps it clear of the library)
        host = document.createElement("div"); host.className = "etip";
        host.style.cssText = "position:absolute;left:var(--inset,0px);right:0;top:calc(50% + 20px);display:flex;justify-content:center";
        E.append(host);
      }
      tip = window.hyTip.show(host, "board", TIPS);   // a visit: the next tip
    };
    // the page settles first (a board with things shows #empty for a moment while it loads): that is not a visit
    const later = () => { clearTimeout(wait); wait = setTimeout(sync, 500); };
    new MutationObserver(later).observe(E, { attributes: true, attributeFilter: ["style"] });
    customElements.whenDefined("hy-tip").then(later);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch, { once: true }); else watch();

  // What is picked, said two ways at once (owner 2026-10-11 on round 21, row 24: ♥ A, and on B «почему нужно выбирать между одним и другим,
  // когда тут можно сделать Б версию с общими командами и А версию с какими-то подсказками такими детальными»; round 20, question 15 began it:
  // «проактивно можно показывать какие-то подсказки, когда что-то выбрал»):
  //   B  the Hint bar at the top (r21/hints-b.html): up to three general keys of this selection, every time, as a reference (stay: never
  //      learned away); it goes as soon as one of them is used or an action begins, as the Hint bar does
  //   A  one tip under the selection (r21/hints-a.html, ui/hy/nudge.js): the first thing of this selection not yet learned, after 1 s
  //      of nothing, gone after 6 s or with any action, learned once its keys are pressed, back when forgotten
  // Only what the board really does: ⌥A (ui/arrange.js, its bar button the long way), ⌘G (ui/boardkeys.js, the right-click menu's Group the
  // long way), ⇧2 (ui/boardzoom.js, its menu the long way), ⇧C (the bar's Crop the long way), ↵ (the card's Studio or Open), a drag begun
  // with ⌥ (canvas.html drag.copy). One selection says it once: a drag, a crop, a Studio or a field in use hide it, and the same selection
  // does not bring it back (a selection that began with a drag says nothing); the Annotation tool too. Both go with Settings › Interface › Key hints and the «?» panel's switch.
  const B = {
    grid: { id: "grid", keys: ["alt+a"], t: "Grid", stay: true }, group: { id: "group", keys: ["mod+g"], t: "Group", stay: true },
    them: { id: "zoom", keys: ["shift+2"], t: "Zoom to them", stay: true }, it: { id: "zoom", keys: ["shift+2"], t: "Zoom to it", stay: true },
    open: { id: "open", keys: ["enter"], t: "Open", stay: true }, crop: { id: "crop", keys: ["shift+c"], t: "Crop", stay: true },
    dup: { id: "dup", keys: ["mod+d"], t: "Duplicate", stay: true },
  };
  const A = {
    grid: { id: "grid", keys: ["alt+a"], t: "<b>lays them out as a grid</b>", long: '[data-tidy="grid"]' },
    group: { id: "group", keys: ["mod+g"], t: "<b>groups them</b>", long: '[data-act="group"]' },
    them: { id: "zoom", keys: ["shift+2"], t: "<b>zooms to them</b>", long: '[data-zoom="sel"]' },
    it: { id: "zoom", keys: ["shift+2"], t: "<b>zooms to it</b>", long: '[data-zoom="sel"]' },
    crop: { id: "crop", keys: ["shift+c"], t: "<b>crops it</b>", long: "[data-crop]" },
    copy: { id: "copy", keys: ["alt"], t: "<b>drag</b>: a copy", auto: false },
  };
  let bar = null, stip = null, skey = "", swait = 0;
  // the selection's box on the screen now (canvas.html bbox and cam), for the tip under it
  const box = () => {
    if (typeof sel === "undefined" || !sel.size || typeof bbox !== "function") return null;
    const ids = [...sel].filter(id => board.items[id] || board.groups[id]); if (!ids.length) return null;
    const b = bbox(ids), r = stage.getBoundingClientRect();
    return { left: (b.x - cam.x) * cam.z + r.left, top: (b.y - cam.y) * cam.z + r.top, right: (b.x + b.w - cam.x) * cam.z + r.left, bottom: (b.y + b.h - cam.y) * cam.z + r.top };
  };
  const end = () => { if (bar) { bar.hide(); bar = null; } if (stip) { stip.hide(); stip = null; } };
  const ssync = () => {
    // canvas.html's own globals (sel, drag, cropState, MODES, board), there once its script has run
    if (typeof sel === "undefined" || typeof board === "undefined" || !window.hyKeyHint || !window.hyNudge) return;
    const a = document.activeElement;
    const busy = !!drag || !!cropState || (MODES && MODES.open !== "board") || (window.hyAnnot && hyAnnot.active) || (a && /^(INPUT|TEXTAREA)$/.test(a.tagName))
      || (a && a.isContentEditable);
    const ids = [...sel].filter(id => board.items[id] || board.groups[id]), k = ids.join();
    if (busy) { end(); if (k) skey = k; return; }   // a selection dragged, cropped, typed into or kept under a tool says nothing, now or after
    if (k === skey) return;
    skey = k; end(); if (!ids.length) return;
    const one = ids.length === 1 ? board.items[ids[0]] : null, pic = !!one && isPic(one);
    const bItems = ids.length > 1 ? [B.grid, B.group, B.them] : pic ? [B.open, B.crop, B.it] : [B.it, B.dup];
    const aItems = ids.length > 1 ? [A.grid, A.group, A.them, A.copy] : pic ? [A.it, A.crop, A.copy] : [A.it, A.copy];
    // the Hint bar is one at a time: another hint up (a note being written, a drag) keeps its place
    if (![...document.querySelectorAll("hy-keyhint[shown]")].some(h => h.dataset.ctx !== "sel")) bar = hyKeyHint.show(stage, "sel", bItems, { place: "top" });
    stip = hyNudge.show("sel", aItems, { rect: box, clear: "#handles .tidy" });   // under the bar over a selection too
  };
  const slater = () => { clearTimeout(swait); swait = setTimeout(ssync, 250); };
  const swatch = () => {
    const H = document.getElementById("handles"), st = document.getElementById("stage"); if (!H || !st) return;
    new MutationObserver(slater).observe(H, { childList: true });
    // the tips' keys and long ways counted with something picked, shown or not (ui/hy/nudge.js learn)
    const learn = () => window.hyNudge ? hyNudge.learn("sel", Object.values(A), () => typeof sel !== "undefined" && sel.size > 0, e => !!(window.hyTyping && hyTyping(e)))
      : setTimeout(learn, 50);
    learn();
    st.addEventListener("pointerdown", e => {
      if (stip) { stip.hide(); stip = null; }
      if (e.altKey && typeof sel !== "undefined" && sel.size && window.hyNudge) hyNudge.used("sel", "copy");   // ⌥ held as a drag begins: a copy
    }, true);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", swatch, { once: true }); else swatch();
  window.HY_BOARD_SEL_HINTS = { bar: B, tip: A };
})();
