// ⌘Z in a text field on the board (owner 2026-10-08: «когда я добавил нотификейшн и нажал cmd + z то значит, я хочу его удалить, и то же
// самое с текстом. Если я, предположим, там заголовок сделал, нажал cmd Z, и значит его нужно просто убрать»). As in Figma and FigJam:
// - a thing made just now (a note, a heading, a timeline or its new dot, a group whose name is open) goes away at the first ⌘Z, however much
//   was typed into it; making it and typing into it are one step, so ⇧⌘Z brings it back with its text and links;
// - in a thing that was there before, ⌘Z undoes the typing inside the field first, as always; once the field is back as it was, the next
//   ⌘Z closes it and undoes the board's step before.
// Before (2026-10-08) the field kept ⌘Z: the browser took the letters back one by one and the new note stayed, and at the field's start
// ⌘Z did nothing at all, because the fields stop their keys and the board's own ⌘Z skips text fields.
// canvas.html calls hyUndoNew.watch(field, fresh, close) right where each editor opens (editNote, editText, editTlLabel, renameGroup):
// fresh true: the thing was made with the field and its step comes when the field closes; "made": its step is already taken (a group,
// whose name joins that step however the field closes: renameGroup drops the name's own step, so a named new group too goes at one ⌘Z);
// close(keep) is the editor's own close: keep true applies what is typed, false leaves the thing as it was. undo and past are canvas.html's.
(() => {
  const isUndo = e => (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && ["z", "я"].includes((e.key || "").toLowerCase());
  function watch(field, fresh, close) {
    const was = field.value; let tried = false;
    field.addEventListener("input", () => { tried = false; });   // typing, or the field's own undo that took something back
    field.addEventListener("keydown", e => {
      if (!isUndo(e)) return;
      const changed = field.value !== was;
      if (!fresh && changed && !tried) { tried = true; return; }   // the field undoes its own typing; a press that changed nothing falls through
      e.preventDefault(); e.stopImmediatePropagation();
      const n = past.length, top = past[n - 1];
      close(!!fresh || changed);
      const step = past.length !== n || past[past.length - 1] !== top;
      if (step && !fresh && !changed) past.pop();   // a step that changed nothing (a field closed as it was) goes
      if (fresh === true && !step) return;   // an empty heading or dot went away with its field: there is nothing else to undo
      // the rest is a ⌘Z on the board: a comment's or a stroke's step in its turn (ui/annotate.js), else the board's own undo
      const again = new KeyboardEvent("keydown", { key: e.key, code: e.code, metaKey: e.metaKey, ctrlKey: e.ctrlKey, bubbles: true, cancelable: true });
      if (document.body.dispatchEvent(again)) undo();   // no one took it (the focus went into another field): the board's undo all the same
    }, true);
  }
  window.hyUndoNew = { watch };
})();
