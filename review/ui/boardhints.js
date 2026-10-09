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
    "ann:select": [{ id: "add", keys: ["shift"], t: "Add to selection" }, { id: "del", keys: ["backspace"], t: "Delete" }, leave],
  };
  // where: on the thing (a note's corner; a field's end, or right after a field as wide as its words), in glass under a drag, in the bar
  const PLACE = { note: { bare: true }, heading: { place: "end", bare: true }, rename: { place: "end", bare: true },
    board: { place: "end", bare: true, after: false }, comment: { place: "end", bare: true, after: false },
    move: { place: "below" }, resize: { place: "below" }, mresize: { place: "below" }, ann: { place: "top" } };
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
})();
