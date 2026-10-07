// Key hints on buttons only while ⌘ is held (owner 2026-10-05: «shortcuts show only when I press cmd, so the interface is not
// overloaded; they must not widen the buttons but appear over them, right aligned, with a darkening gradient under them»).
// A key cap that is a button's own child (<button>Упорядочить <kbd>⌥A</kbd></button>) takes no room: it lies over the button's right
// end, hidden; holding ⌘ fades it in with a gradient of the button's ground under it. Menus keep their key column (.mk), as on the Mac.
// The board inside the library is another document: the state is passed to the parent and to same-origin frames, so ⌘ held over
// either shows the hints in both.
(() => {
  if (window.hyKeyHints) return;
  const css = `
button:has(> kbd) { position: relative; }
button > kbd { position: absolute !important; right: 6px; top: 50%; translate: 0 -50%; margin: 0 !important; z-index: 2; pointer-events: none;
  opacity: 0; scale: .92; transition: opacity .16s cubic-bezier(.32,.72,0,1), scale .2s cubic-bezier(.32,.72,0,1); }
button:has(> kbd)::after { content: ""; position: absolute; inset: 0; z-index: 1; border-radius: inherit; pointer-events: none; opacity: 0;
  background: linear-gradient(to right, transparent 20%, color-mix(in srgb, var(--panel, #18181b) 94%, transparent) 72%);
  transition: opacity .16s cubic-bezier(.32,.72,0,1); }
:root.hy-keys button > kbd { opacity: 1; scale: 1; }
:root.hy-keys button:has(> kbd)::after { opacity: 1; }
@media (prefers-reduced-motion: reduce) { button > kbd, button:has(> kbd)::after { transition: opacity .1s; scale: 1; } }`;
  const st = document.createElement("style"); st.textContent = css; (document.head || document.documentElement).appendChild(st);
  const docs = () => {
    const out = [document];
    try { if (parent !== window && parent.document) out.push(parent.document); } catch {}
    for (const f of document.querySelectorAll("iframe")) { try { if (f.contentDocument) out.push(f.contentDocument); } catch {} }
    return out;
  };
  let on = false, t = 0, quiet = false;
  const set = v => { clearTimeout(t); if (v === on) return; on = v; docs().forEach(d => d.documentElement.classList.toggle("hy-keys", v)); };
  window.hyKeyHints = set;
  // the hints come after ⌘ is held a moment, and not at all while ⌘ zooms with the wheel (owner 2026-10-06: the key caps covered the
  // selection bar's words during a ⌘ + scroll zoom); a ⌘ shortcut pressed before that never flashes them
  addEventListener("keydown", e => {
    if (e.key === "Meta") { if (!quiet && !on) { clearTimeout(t); t = setTimeout(() => set(true), 220); } }
    else if (!on) clearTimeout(t); else if (!e.metaKey) set(false);
  }, true);
  addEventListener("keyup", e => { if (e.key === "Meta" || !e.metaKey) { quiet = false; set(false); } }, true);
  addEventListener("wheel", e => { if (e.metaKey) { quiet = true; set(false); } }, { capture: true, passive: true });
  // a ⌘ shortcut that moves the focus elsewhere (⌘Tab, a menu) never sends the key up here
  addEventListener("blur", () => set(false));
  document.addEventListener("visibilitychange", () => { if (document.hidden) set(false); });
  addEventListener("pointermove", e => { if ((on || t) && !e.metaKey) { quiet = false; set(false); } }, { passive: true });
})();
