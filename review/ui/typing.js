// The one rule for keys while someone types (owner 2026-10-10: «когда я в аннотациях пишу что-то, у меня триггерится F кнопка, возможно и
// другие тоже»): no shortcut of the app or a plugin fires while the focus is in a field that takes text. Such a field is a text input, a
// textarea, an editable element (contenteditable, also plaintext-only) or [role=textbox], found through shadow roots and our same-origin
// frames. A slider, a checkbox, a button or a select with the focus is not one: ⌘Z and the arrows stay the board's there. Esc, Enter and
// ⌘↵ are the field's own (its keydown handles them).
//
//   hyTyping(e)        true while the key event e (or, without e, the keyboard now) goes into such a field: every key handler asks this
//   hyTyping.field(el) is el such a field
//   hyTyping.active()  the element with the focus, inside shadow roots and same-origin frames
//   hyTyping.ownKey(e) the key belongs to the control with the focus (Space on a checkbox, a select's letters): the shortcuts leave it
//   hyTyping.global(e) ⌘M (the library), ⌘. (hide the interface) and ⌘F (the library's search): the app's own keys, the only ones that act
//                      while you type too (P4 B-35, the documented allow-list); every other shortcut asks hyTyping(e) and waits
//   hyTyping.keys(el, o) Esc, ↵ and Tab of one field, the same rule in every field of the board and of a Studio (owner 2026-10-10, below)
//
// Esc in a field (owner decision 2026-10-10, П4 B-15, option (b), Figma's split): what you write on the canvas keeps its text, Esc applies
// it as ↵ does (a note, a heading, a text document, a group's title, a timeline's label, an arrow's words; an annotation keeps its words as
// a draft on its pin); a name or a value goes back to what it was (the board's name, a page's name, Dev Studio's tree and Inspector, an
// attribute, a number, a colour, a version's name). o: { esc: "apply" | "cancel", apply(e), cancel(e) (esc "cancel"), enter, tab, key(e) }
//   enter  "shift" (default) ↵ and ⌘↵ apply, ⇧↵ is the field's new line | "line" ↵ applies | "mod" ↵ is a new line, ⌘↵ applies | "none"
//   tab    "apply" (default) Tab applies and gives the keys back to the board (P4 B-25: the focus fell on the dock's next button and the
//          next ↵ made a note) | "own" the field's own Tab (a document's indent)
//   key    every other key, after these (⌘B, a list's ⇧↵); before(e) first, true when it took the key (a mention list's ↵ and Esc)
//   primary(e) a Studio's field: ⌘↵ applies, then runs the Studio's primary action (Save, Done; P4 S-28, ⌘↵ is that action everywhere)
// A key an input method still composes (↵ picking a word) is the input method's (P4 B-50). The field takes every key (stopPropagation).
(() => {
  const NOT_TEXT = /^(range|checkbox|radio|button|submit|reset|color|file|image|hidden)$/i;
  const field = el => !!el && el.nodeType === 1 && (el.isContentEditable || el.tagName === "TEXTAREA"
    || (el.tagName === "INPUT" && !NOT_TEXT.test(el.type)) || (el.getAttribute("role") || "").toLowerCase() === "textbox");
  function active(doc = document) {
    let a = doc.activeElement;
    for (let i = 0; a && i < 16; i++) {
      if (a.shadowRoot && a.shadowRoot.activeElement) { a = a.shadowRoot.activeElement; continue; }
      if (a.tagName === "IFRAME" || a.tagName === "FRAME") {
        let d = null; try { d = a.contentDocument; } catch { /* another origin: its keys never come here */ }
        if (d && d.activeElement && d.activeElement !== d.body) { a = d.activeElement; continue; }
      }
      break;
    }
    return a;
  }
  function typing(e) {
    if (e && e.isComposing) return true;   // an input method still composing a letter
    const path = e && e.composedPath ? e.composedPath() : [];
    if (path.length && field(path[0])) return true;
    if (e && e.target && field(e.target)) return true;
    return field(active());
  }
  // the key a control with the focus (from the keyboard: the mouse lets go of it below) answers itself: Space and ↵ press a button, a
  // checkbox, a radio; a select its letters and arrows; a slider its arrows. ⌘ keys are never its own
  function ownKey(e) {
    const a = active(), k = e && e.key; if (!a || !a.matches || field(a) || e.metaKey || e.ctrlKey) return false;
    if (a.tagName === "SELECT") return true;
    if ((a.type === "range" || (a.getAttribute("role") || "") === "slider") && /^(Arrow|Page|Home|End)/.test(k)) return true;
    return (k === " " || k === "Enter") && a.matches("button, input, [role=button], [role=checkbox], [role=switch], [role=radio], [role=tab]");
  }
  // ⌘M ⌘. ⌘F, by the physical key or the letter in either layout, no ⇧ or ⌥: the app's keys in any field (P4 B-35)
  const GLOBAL = { KeyM: ["m", "ь"], Period: [".", "ю"], KeyF: ["f", "а"] };
  function global(e) {
    if (!e || !(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return false;
    const k = String(e.key || "").toLowerCase();
    return Object.entries(GLOBAL).some(([code, ks]) => e.code === code || ks.includes(k));
  }
  // the keys back to the board (or the page): the field lets go, the window takes them
  function toBoard() { const a = active(); if (a && a.blur && a !== document.body) a.blur(); try { window.focus(); } catch { /* a closed frame */ } }
  function keys(el, o) {
    const h = e => {
      if (o.stop !== false) e.stopPropagation();
      if (e.isComposing || e.keyCode === 229 || (o.before && o.before(e))) return;
      const mod = e.metaKey || e.ctrlKey, en = o.enter || "shift";
      if (e.key === "Escape") { e.preventDefault(); (o.esc === "cancel" ? o.cancel || o.apply : o.apply)(e); return; }
      if (e.key === "Enter" && en !== "none" && (en === "line" || mod || (en === "shift" && !e.shiftKey))) {
        e.preventDefault(); o.apply(e); if (mod && o.primary) { toBoard(); o.primary(e); } return;
      }
      if (e.key === "Tab" && o.tab !== "own" && !mod && !e.altKey) { e.preventDefault(); o.apply(e); toBoard(); return; }
      if (o.key) o.key(e);
    };
    el.addEventListener("keydown", h);
    return h;
  }
  typing.field = field; typing.active = active; typing.ownKey = ownKey; typing.global = global; typing.keys = keys; typing.toBoard = toBoard;
  window.hyTyping = typing;
  // a control touched with the mouse gives the keys back (P4 S-15, П4 audit 2026-10-10: after a checkbox, a slider or a Studio's control
  // the board's and the Studio's keys were dead until a click on the canvas): let go, it loses the focus unless its click moved the focus
  // on (a menu) or it sits in a dialog; a select once it changed. A field you type into keeps it
  const CONTROL = "input, button, select, [role=slider], [role=switch], [role=checkbox], [role=radio], [role=tab], [tabindex]";
  addEventListener("pointerup", () => {
    const a = active(); if (!a || a === document.body || field(a) || a.tagName === "SELECT" || !a.matches || !a.matches(CONTROL)) return;
    if (a.closest("[role=dialog], [role=alertdialog], [aria-modal=true], #hyConfirm")) return;
    setTimeout(() => { if (active() === a && a.blur) a.blur(); }, 0);
  }, true);
  addEventListener("change", e => { if (e.target && e.target.tagName === "SELECT") e.target.blur(); }, true);
})();
