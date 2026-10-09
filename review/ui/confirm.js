// One question before something is lost, the image studio's (hyimg-frames editor/index.html openDialog, «Close without saving?»): a small
// glass dialog in the middle of the window, in the dialog layer (the notes stay at the top), that only its answer closes (owner
// 2026-10-07: the 3D studio's question hid behind a newer notification). The 3D studio asks with it; its look is the image studio's dialog: title, a footnote, Cancel and the
// action, Enter the action, Esc or a press beside it Cancel. The keys go to it alone while it is open. Its classes are hc-* (the board's
// .note is a sticky note)
//   import("/ui/confirm.js").then(m => m.hyConfirm({ title, note, ok, cancel, icon, onOk, onCancel }))   (also window.hyConfirm)
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
#hyConfirm .hc-btns { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
#hyConfirm button { height: 28px; padding: 0 10px; border: 0; border-radius: var(--hy-row-r, 8px); background: var(--raise); box-shadow: inset 0 0 0 1px var(--line);
  color: var(--ink); font: 400 12.5px var(--sans, system-ui); cursor: pointer; white-space: nowrap; }
#hyConfirm button:hover { background: var(--raise2, var(--raise)); } #hyConfirm button:active { transform: scale(.97); }
#hyConfirm button.ok { background: var(--ink); color: var(--panel); box-shadow: none; font-weight: 600; } #hyConfirm button.ok:hover { opacity: .88; }
/* asked inside a Studio, the action is in the Studio's colour, white words (ui/modes.js --hy-studio; owner 2026-10-09 on a white Discard:
   «Она должна быть такого цвета, в каком режиме мы сейчас находимся»); Cancel stays as it is */
:root[data-studio] #hyConfirm button.ok { background: var(--hy-studio); color: var(--hy-on-accent, #fff); }
@media (prefers-reduced-motion: reduce) { #hyConfirm, #hyConfirm .hc-box { transition: none; } }`;
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function hyConfirm(o) {
  const old = document.getElementById("hyConfirm"); if (old) old._close(null);
  if (!document.getElementById("hyConfirmCss")) { const st = document.createElement("style"); st.id = "hyConfirmCss"; st.textContent = CSS; document.head.appendChild(st); }
  const w = document.createElement("div"); w.id = "hyConfirm"; w.setAttribute("role", "alertdialog"); w.setAttribute("aria-modal", "true");
  const icon = o.icon !== false && window.hyIcon ? window.hyIcon(o.icon || "close", 16, 2) : "";
  w.innerHTML = `<div class="hc-box"><div class="hc-t">${icon}<span>${esc(o.title)}</span></div>${o.note ? `<div class="hc-note">${esc(o.note)}</div>` : ""}`
    + `<div class="hc-btns"><button type="button" data-a="no">${esc(o.cancel || "Cancel")}</button><button type="button" class="ok" data-a="ok">${esc(o.ok || "OK")}</button></div></div>`;
  let done = false;
  const keys = e => {   // the dialog's keys only, before the page's (the 3D studio's Esc would ask again)
    e.stopImmediatePropagation();
    if (e.key === "Escape") { e.preventDefault(); close(false); } else if (e.key === "Enter") { e.preventDefault(); close(true); }
  };
  const close = yes => {
    if (done) return; done = true; removeEventListener("keydown", keys, true);
    w.classList.remove("on"); setTimeout(() => w.remove(), 220);
    if (yes === true && o.onOk) o.onOk(); else if (yes === false && o.onCancel) o.onCancel();
  };
  w._close = close;
  w.addEventListener("pointerdown", e => { e.stopPropagation(); if (e.target === w) close(false); });
  w.addEventListener("click", e => { const b = e.target.closest("[data-a]"); if (b) close(b.dataset.a === "ok"); });
  addEventListener("keydown", keys, true);
  document.body.appendChild(w); requestAnimationFrame(() => w.classList.add("on"));
  setTimeout(() => { const b = w.querySelector("[data-a=ok]"); if (b) b.focus(); }, 60);
  return { close: () => close(null) };
}
window.hyConfirm = hyConfirm;
