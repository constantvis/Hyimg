// An undo step for a change that lives outside the board's own snapshot (P4 B-26 ♥, B-49 a page's name, П4 audit 2026-10-10): ⌘Z took
// the step before it instead, one you could not see. The board's steps are its JSON strings in canvas.html past / future; such a step is
// the board as it is now, marked so it never equals another string, with what to do on ⌘Z and ⇧⌘Z beside it. canvas.html's undo and redo
// restore the board (no change) and call run(), which does the change back or again and moves the mark to the string the other stack got.
//   hyUndoFx.push({ undo, redo, label }) a step on top of past, the redo stack cleared, as commit does; label: its name over Undo
//   hyUndoFx.label(s)                    that name for a string of past or future, "" for the board's own steps (ui/boarddock.js)
//   hyUndoFx.run(s, other, dir)          canvas.html xmoveStep: s the string ⌘Z (dir "undo") or ⇧⌘Z ("redo") took; true when it was ours
// Every step's note (round 20 B-12 and undo-a; round 21, owner 2026-10-11 on r21/undo-config.html: «Вещи шага миниатюрами»): canvas.html
// commit and the steps outside the snapshot say what they did through one helper, right after the step is on past. The note gets Undo
// (it works while that step is the newest) and the step's pictures as tiles; opt.step names the step by its command («Arrange as a grid»,
// «Duplicate»), so the dock's Undo says that and not what the strings differ in («Move 5»).
//   hyUndoFx.note(text, opt)             opt: hyToast's (kind, key, actions), step (the name), paths (the pictures of a step outside the
//                                        snapshot, ♥); an empty text only names the step
//   hyUndoFx.things(sa, sb)              the pictures two board strings differ in, { urls, more }: the note's tiles, the dock's plate
(() => {
  if (window.hyUndoFx) return;
  const FX = new Map(); let n = 0;
  const NAMES = new Map();   // a board step's string -> its command's name; it goes to the other stack with the step
  const tag = s => { const o = JSON.parse(s); o.fx = ++n; return JSON.stringify(o); };
  function push(fx) {
    const s = tag(snap()); past.push(s); if (past.length > 200) FX.delete(past.shift()); future = [];
    FX.set(s, { fx, dir: "undo" }); render();   // the dock's ⌘Z button wakes up
  }
  function run(s, other, dir) {
    const nm = NAMES.get(s); NAMES.delete(s);
    const x = FX.get(s), ours = !!x && x.dir === dir;
    if (ours) { FX.delete(s); const k = tag(other[other.length - 1]); other[other.length - 1] = k; FX.set(k, { fx: x.fx, dir: dir === "undo" ? "redo" : "undo" }); }
    if (nm) NAMES.set(other[other.length - 1], nm);
    if (!ours) return false;
    try { x.fx[dir](); } catch (e) { console.error("undo step", e); }
    return true;
  }
  const label = s => { const x = FX.get(s); return (x && x.fx.label) || NAMES.get(s) || ""; };

  // ---- the step's note ----------------------------------------------------------------------------------------------------------------
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/^\w+::/, ""));
  const NONE = { urls: [], more: 0 };
  const thumb = p => (typeof thumbUrl === "function" ? thumbUrl(p, 96) : "");
  const picOf = it => (it && !it.type && it.path ? thumb(typeof pgKey === "function" ? pgKey(it) : it.path) : "");
  const tiles = urls => { const u = [...new Set(urls.filter(Boolean))]; return { urls: u.slice(0, 3), more: Math.max(0, u.length - 3) }; };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function things(sa, sb) {
    let A, B; try { A = JSON.parse(sa).items || {}; B = JSON.parse(sb).items || {}; } catch { return NONE; }
    const ids = [...Object.keys(B).filter(k => !A[k] || !same(A[k], B[k])), ...Object.keys(A).filter(k => !B[k])];
    return tiles(ids.map(k => picOf(B[k] || A[k])));
  }
  function note(text, opt = {}) {
    if (typeof past === "undefined" || !past.length) return null;
    const s = past[past.length - 1];
    if (opt.step) { NAMES.set(s, opt.step); while (NAMES.size > 400) NAMES.delete(NAMES.keys().next().value); }
    if (!text || typeof toast !== "function") return null;
    const th = opt.paths ? tiles(opt.paths.map(thumb)) : FX.has(s) ? NONE : things(s, snap());
    const undoIt = { label: T("Undo"), fn: () => { if (past[past.length - 1] === s) undo(); } };
    const { step, paths, ...o } = opt;
    return toast(text, o.kind, { ...o, things: th.urls, more: th.more, actions: [...(o.actions || []), undoIt] });
  }
  window.hyUndoFx = { push, run, label, note, things };
})();
