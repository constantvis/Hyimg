// An undo step for a change that lives outside the board's own snapshot (P4 B-26 ♥, B-49 a page's name, П4 audit 2026-10-10): ⌘Z took
// the step before it instead, one you could not see. The board's steps are its JSON strings in canvas.html past / future; such a step is
// the board as it is now, marked so it never equals another string, with what to do on ⌘Z and ⇧⌘Z beside it. canvas.html's undo and redo
// restore the board (no change) and call run(), which does the change back or again and moves the mark to the string the other stack got.
//   hyUndoFx.push({ undo, redo })       a step on top of past, the redo stack cleared, as commit does
//   hyUndoFx.run(s, other, dir)          canvas.html xmoveStep: s the string ⌘Z (dir "undo") or ⇧⌘Z ("redo") took; true when it was ours
(() => {
  if (window.hyUndoFx) return;
  const FX = new Map(); let n = 0;
  const tag = s => { const o = JSON.parse(s); o.fx = ++n; return JSON.stringify(o); };
  function push(fx) {
    const s = tag(snap()); past.push(s); if (past.length > 200) FX.delete(past.shift()); future = [];
    FX.set(s, { fx, dir: "undo" }); render();   // the dock's ⌘Z button wakes up
  }
  function run(s, other, dir) {
    const x = FX.get(s); if (!x || x.dir !== dir) return false;
    FX.delete(s); const k = tag(other[other.length - 1]); other[other.length - 1] = k; FX.set(k, { fx: x.fx, dir: dir === "undo" ? "redo" : "undo" });
    try { x.fx[dir](); } catch (e) { console.error("undo step", e); }
    return true;
  }
  window.hyUndoFx = { push, run };
})();
