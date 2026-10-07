// A 3D file in the library's viewer (owner 2026-10-07, project «Field Kit»: STEP files in «modeling C4D», «я не могу их смотреть через
// наш 3D просмотрщик»). The library lists 3D files in their folders (review/lib3d.py) and a click opens the viewer as for any file; for a
// 3D file the picture gives way to the model itself, drawn by the 3D plugin (its sprites module's view(): three.js, the STEP converted by
// FreeCAD first), with «Put on the board» to make a 3D card of it. v2.html calls hyLib3d.view(item) on every open and view(null) on close.
// Without the plugin the box says that the 3D plugin draws 3D files.
(() => {
  let box = null, live = null, cur = null;
  const T_ = (k, v) => (window.T ? T(k, v) : k);
  const css = `
    .v3d { position: absolute; inset: 24px; border-radius: 14px; overflow: hidden; touch-action: none; cursor: grab;
      background: radial-gradient(120% 90% at 50% 35%, var(--panel) 0%, var(--raise) 75%); }   /* the library tile's ground (.card.m3d .m3s) */
    .v3d:active { cursor: grabbing; } .v3d[hidden] { display: none; }
    .stage.v3don :is(#hint2, #ntog, #pop) { display: none !important; }   /* marks and comments on an area are for pictures */
    @media (min-width: 761px) { .v3d { right: 444px; } }
    .v3d .v3d-gl { position: absolute; inset: 0; display: block; }
    .v3d .v3d-note { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); max-width: 70%; text-align: center;
      color: var(--sub); font: 500 14px/1.4 var(--sans, system-ui); text-wrap: balance; pointer-events: none; }
    .v3d:is([data-state=converting], [data-state=loading]) .v3d-note::before { content: ""; display: block; width: 22px; height: 22px; margin: 0 auto 10px;
      border-radius: 50%; border: 2px solid var(--line); border-top-color: var(--sub); animation: v3dspin 1s linear infinite; }
    @keyframes v3dspin { to { transform: rotate(1turn); } }
    @media (prefers-reduced-motion: reduce) { .v3d .v3d-note::before { animation: none; } }
    .v3d .v3d-bar { position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; white-space: nowrap;
      z-index: 2; color: var(--sub); font: 500 12px var(--sans, system-ui); }
    .v3d .v3d-bar button { height: 30px; padding: 0 14px; border: 0; border-radius: 999px; background: var(--ink); color: var(--on-ink);
      font: 600 12px var(--sans, system-ui); cursor: pointer; }
    .v3d .v3d-bar button:hover { opacity: .85; }`;
  function make() {
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    box = document.createElement("div"); box.className = "v3d"; box.hidden = true;
    // the viewer's own gestures (zoom of the picture, marks, the swipe to the next frame) are not for the model: they stay inside
    for (const ev of ["pointerdown", "mousedown", "wheel", "dblclick", "click", "gesturestart", "gesturechange", "touchstart"]) box.addEventListener(ev, e => e.stopPropagation());
    const stage = document.querySelector("#viewer .stage"); stage.insertBefore(box, stage.firstChild);   // first: the arrows and the page bar stay over it
  }
  function view(i) {
    const on = !!(i && i.kind === "model"), frame = document.getElementById("frame");
    if (on && cur === i && live) return;   // the same file again (a rating saved, the list redrawn)
    if (live) { live.then(v => v && v.close()); live = null; }
    cur = on ? i : null;
    if (frame) frame.style.visibility = on ? "hidden" : "";
    const stage = document.querySelector("#viewer .stage"); if (stage) stage.classList.toggle("v3don", on);
    if (!on) { if (box) { box.hidden = true; box.textContent = ""; } return; }
    if (!box) make();
    box.hidden = false; box.textContent = ""; delete box.dataset.state;
    const bar = document.createElement("div"); bar.className = "v3d-bar";
    bar.innerHTML = `<span></span><button type="button"></button>`;
    bar.firstChild.textContent = T_("Drag to turn · scroll to zoom");
    bar.lastChild.textContent = T_("Put on the board"); bar.lastChild.title = T_("A 3D card of this file on the board: turn it, light it, render it in the 3D studio");
    bar.lastChild.onclick = () => { const it = cur; if (typeof closeV === "function") closeV(); if (it && typeof pick3d === "function") pick3d(it); };
    box.appendChild(bar);
    const mod = typeof spritesMod === "function" ? spritesMod() : Promise.resolve(null);
    live = mod.then(m => {
      if (cur !== i) return null;
      if (!m || !m.view) {
        box.dataset.state = "failed"; const n = document.createElement("div"); n.className = "v3d-note";
        n.textContent = T_("The 3D plugin shows 3D files: it is not installed"); box.prepend(n); return null;
      }
      return m.view(box, i, { t: T_, alive: () => cur === i });
    }).catch(e => { console.error("3D viewer", e); return null; });
  }
  window.hyLib3d = { view };
})();
