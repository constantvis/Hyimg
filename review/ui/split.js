// One splitter between stacked panel sections (owner 2026-10-06: the 3D editor's Objects, Lights and Cameras need «a draggable handle
// between sections to make one section larger and another smaller, like the image editor already does», one component for both). It is
// the frame editor's line between its two panel groups, taken out of that page. Its look is round 12's «A · Line» (owner 2026-10-09): a
// hairline, under the pointer a 3 px line of the accent (--hy-acc); .hy-split-gap is the gap between two blocks, nothing in it at rest.
// A vertical drag moves it, a double click gives the sizes back to the content. The host decides what moving it means.
//   hySplit(el, { start(e) -> ctx, move(dy, ctx, e), end(ctx), reset() })
// el gets the class .hy-split (the look below); .off on it hides it and makes it inert (a folded neighbour). The pointer is captured, so
// the drag goes on outside the line; while it runs the page has .hy-splitting (hosts turn their height transitions off with it).
// Used by the frame editor (hyimg-frames editor/index.html #split) and the 3D editor's layer list (hyimg-3d-studio engine.js).
(() => {
  if (window.hySplit) return;
  const css = `
.hy-split { position: relative; flex: none; height: 9px; box-sizing: border-box; cursor: row-resize; touch-action: none; transition: opacity .25s cubic-bezier(.32,.72,0,1); }
.hy-split::before { content: ""; position: absolute; left: 4px; right: 4px; top: 4px; height: 1px; border-radius: 2px; background: var(--hy-pline, var(--line, rgba(127,127,127,.25)));
  pointer-events: none; transition: background-color .18s cubic-bezier(.32,.72,0,1), top .18s cubic-bezier(.32,.72,0,1), height .18s cubic-bezier(.32,.72,0,1); }
.hy-split:hover::before, .hy-split.drag::before { top: 3px; height: 3px; background: var(--hy-acc, var(--sel, #3b82f6)); }
.hy-split.hy-split-gap::before { background: transparent; }
.hy-split.hy-split-gap:hover::before, .hy-split.hy-split-gap.drag::before { background: var(--hy-acc, var(--sel, #3b82f6)); }
.hy-split.off { opacity: 0; pointer-events: none; }
:root.hy-splitting, :root.hy-splitting * { cursor: row-resize !important; }
@media (prefers-reduced-motion: reduce) { .hy-split, .hy-split::after { transition: none; } }`;
  const st = document.createElement("style"); st.textContent = css; (document.head || document.documentElement).appendChild(st);
  window.hySplit = (el, o = {}) => {
    el.classList.add("hy-split");
    let d = null;
    const stop = () => {
      if (!d) return; const was = d; d = null;
      el.classList.remove("drag"); document.documentElement.classList.remove("hy-splitting");
      if (o.end) o.end(was.ctx);
    };
    el.addEventListener("pointerdown", e => {
      if (e.button !== 0 || el.classList.contains("off")) return;
      e.preventDefault(); e.stopPropagation(); el.setPointerCapture(e.pointerId);
      d = { y: e.clientY, ctx: o.start ? o.start(e) : null };
      el.classList.add("drag"); document.documentElement.classList.add("hy-splitting");
    });
    el.addEventListener("pointermove", e => { if (d && o.move) o.move(e.clientY - d.y, d.ctx, e); });
    el.addEventListener("pointerup", stop); el.addEventListener("pointercancel", stop); el.addEventListener("lostpointercapture", stop);
    el.addEventListener("dblclick", e => { e.preventDefault(); e.stopPropagation(); if (o.reset) o.reset(); });   // back to the content's own sizes
    return el;
  };
})();
