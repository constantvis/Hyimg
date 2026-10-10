// One question before something is lost, the image studio's (hyimg-image-studio editor/index.html openDialog, «Close without saving?»): a small
// glass dialog in the middle of the window, in the dialog layer (the notes stay at the top), that only its answer closes (owner
// 2026-10-07: the 3D studio's question hid behind a newer notification). The 3D studio asks with it; its look is the image studio's dialog: title, a footnote, Cancel and the
// action, Enter the action, Esc or a press beside it Cancel. The keys go to it alone while it is open. Its classes are hc-* (the board's
// .note is a sticky note)
//   import("/ui/confirm.js").then(m => m.hyConfirm({ title, note, ok, cancel, icon, onOk, onCancel, save, safe, accent }))   (also window.hyConfirm)
// A Studio's «Close without saving?» (P4 S-03, П4 audit 2026-10-10: ↵ and ⌘↵ in it threw the work away) passes save: {label, run}, a third
// answer, the primary one and ⌘↵'s; then, or with safe: true, the safe answer (cancel, «Keep editing») has the focus and ↵, the action
// (ok, «Discard») stands apart on the left. ↵ presses the button with the focus, Tab stays in the dialog, the focus goes back after it
const CSS = `
#hyConfirm { position: fixed; inset: 0; z-index: 99; display: grid; place-items: center; background: color-mix(in srgb, var(--panel, #0c0c0e) 30%, transparent);
  opacity: 0; transition: opacity .22s cubic-bezier(.32,.72,0,1); }
#hyConfirm.on { opacity: 1; }
#hyConfirm .hc-box { width: 320px; box-sizing: border-box; padding: 14px; border-radius: var(--hy-panel-r, 14px); border: 1px solid var(--line, rgba(255,255,255,.1));
  background: color-mix(in srgb, var(--panel, #0c0c0e) 86%, transparent); -webkit-backdrop-filter: blur(18px) saturate(1.4); backdrop-filter: blur(18px) saturate(1.4);
  box-shadow: var(--plate-sh, 0 14px 40px rgba(0,0,0,.5)); color: var(--ink, #fafafa); font: 400 13px/1.4 var(--sans, -apple-system, system-ui, sans-serif);
  transform: translateY(8px) scale(.98); transition: transform .26s cubic-bezier(.32,.72,0,1); }
#hyConfirm.on .hc-box { transform: none; }
#hyConfirm .hc-t { font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; } #hyConfirm .hc-t svg { color: var(--sub); flex: none; }
#hyConfirm .hc-note { font: 400 11px/1.35 var(--sans, system-ui); letter-spacing: .01em; color: var(--hy-hint, var(--muted, #a1a1aa)); }
#hyConfirm .hc-btns { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; } #hyConfirm .hc-sp { flex: 1; }
#hyConfirm button { height: 28px; padding: 0 10px; border: 0; border-radius: var(--hy-row-r, 8px); background: var(--raise); box-shadow: inset 0 0 0 1px var(--line);
  color: var(--ink); font: 400 12.5px var(--sans, system-ui); cursor: pointer; white-space: nowrap; }
#hyConfirm button:hover { background: var(--raise2, var(--raise)); } #hyConfirm button:active { transform: scale(.97); }
#hyConfirm button.ok { background: var(--ink); color: var(--panel); box-shadow: none; font-weight: 600; } #hyConfirm button.ok:hover { opacity: .88; }
/* asked inside a Studio, the action is in the Studio's colour, white words (ui/modes.js --hy-studio; owner 2026-10-09 on a white Discard:
   «Она должна быть такого цвета, в каком режиме мы сейчас находимся»); Cancel stays as it is */
:root[data-studio] #hyConfirm button.ok { background: var(--hy-studio); color: var(--hy-on-accent, #fff); }
#hyConfirm[data-accent] button.ok { background: var(--hc-accent); color: var(--hy-on-accent, #fff); }   /* o.accent: a Studio's page of its own */
@media (prefers-reduced-motion: reduce) { #hyConfirm, #hyConfirm .hc-box { transition: none; } }`;
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function hyConfirm(o) {
  const old = document.getElementById("hyConfirm"); if (old) old._close(null);
  if (!document.getElementById("hyConfirmCss")) { const st = document.createElement("style"); st.id = "hyConfirmCss"; st.textContent = CSS; document.head.appendChild(st); }
  const w = document.createElement("div"); w.id = "hyConfirm"; w.setAttribute("role", "alertdialog"); w.setAttribute("aria-modal", "true");
  const save = o.save && o.save.run ? o.save : null, safe = !!(save || o.safe), back = document.activeElement;
  if (o.accent) { w.dataset.accent = ""; w.style.setProperty("--hc-accent", o.accent); }
  const icon = o.icon !== false && window.hyIcon ? window.hyIcon(o.icon || "close", 16, 2) : "";
  w.innerHTML = `<div class="hc-box"><div class="hc-t">${icon}<span>${esc(o.title)}</span></div>${o.note ? `<div class="hc-note">${esc(o.note)}</div>` : ""}`
    + `<div class="hc-btns">${save ? `<button type="button" data-a="ok">${esc(o.ok || "OK")}</button><span class="hc-sp"></span>` : ""}`
    + `<button type="button" data-a="no">${esc(o.cancel || "Cancel")}</button>`
    + (save ? `<button type="button" class="ok" data-a="save">${esc(save.label || "Save")}</button>` : `<button type="button" class="ok" data-a="ok">${esc(o.ok || "OK")}</button>`) + `</div></div>`;
  let done = false;
  const btns = () => [...w.querySelectorAll("button[data-a]")], answer = b => close(b.dataset.a === "save" ? "save" : b.dataset.a === "ok");
  const keys = e => {   // the dialog's keys only, before the page's (the 3D studio's Esc would ask again); every other key waits
    e.stopImmediatePropagation(); if (e.isComposing) return;
    const mod = e.metaKey || e.ctrlKey, f = w.contains(document.activeElement) && document.activeElement.closest("button[data-a]");
    if (e.key === "Escape") { e.preventDefault(); close(false); }
    else if (e.key === "Enter" && mod) { e.preventDefault(); if (save) close("save"); }   // ⌘↵ saves, never the action
    else if (e.key === "Enter" && !e.altKey && !e.shiftKey) { e.preventDefault(); if (f) answer(f); else close(safe ? false : true); }
    else if (e.key === "Tab") { e.preventDefault(); const l = btns(), i = l.indexOf(f); l[(i + (e.shiftKey ? -1 : 1) + l.length) % l.length].focus(); }
    else if (!["Shift", "Meta", "Control", "Alt"].includes(e.key)) e.preventDefault();
  };
  const close = yes => {
    if (done) return; done = true; removeEventListener("keydown", keys, true);
    w.classList.remove("on"); setTimeout(() => w.remove(), 220);
    if (w.contains(document.activeElement)) { if (back && back.isConnected && back !== document.body && back.focus) back.focus(); else document.activeElement.blur(); }
    if (yes === "save") save.run(); else if (yes === true && o.onOk) o.onOk(); else if (yes === false && o.onCancel) o.onCancel();
  };
  w._close = close;
  w.addEventListener("pointerdown", e => { e.stopPropagation(); if (e.target === w) close(false); });
  w.addEventListener("click", e => { const b = e.target.closest("[data-a]"); if (b) answer(b); });
  addEventListener("keydown", keys, true);
  document.body.appendChild(w); requestAnimationFrame(() => w.classList.add("on"));
  setTimeout(() => { const b = w.querySelector(safe ? "[data-a=no]" : "[data-a=ok]"); if (b && !done) b.focus(); }, 60);
  return { close: () => close(null) };
}
window.hyConfirm = hyConfirm;
// The one question before a Studio's unsaved work is left (owner decision 2026-10-10, P4 S-26 A): every exit that asks, in Image Studio, 3D
// Studio and Dev Studio, asks this, in the same words: «Keep editing» (the focus, ↵ and Esc), «Discard» apart, «Save» the primary and ⌘↵.
// Only a Studio's Cancel button and Image Studio's crumb ask; the last Esc, the Board segment and another Studio's segment keep the work
// (S-27 A). The words are the board's (window.T, the parent's in Image Studio's page)
//   hyLeave({ name, save, discard, keep, accent })   save, discard, keep: what each answer does; name: the thing's name in the title
export function hyLeave(o) {
  const T = typeof window.T === "function" ? window.T : (() => { try { return parent !== window && typeof parent.T === "function" ? parent.T : null; } catch { return null; } })();
  const w = (k, v) => T ? T(k, v) : k.replace(/\{(\w+)\}/g, (_, n) => (v || {})[n] ?? "");
  return hyConfirm({ title: o.name ? w("Save changes to “{name}”?", { name: o.name }) : w("Save changes?"), note: w("Your changes are lost if you leave without saving"),
    ok: w("Discard"), cancel: w("Keep editing"), onOk: o.discard, onCancel: o.keep, accent: o.accent, icon: o.icon, save: { label: w("Save"), run: o.save } });
}
window.hyLeave = hyLeave;
// the question as a promise: true for the action, false for Cancel, Esc or a press beside it (the board's page delete, a big drop, P4 B-57)
export const ask = o => new Promise(ok => { hyConfirm({ ...o, onOk: () => ok(true), onCancel: () => ok(false) }); });
