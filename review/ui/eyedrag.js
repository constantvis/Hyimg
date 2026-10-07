// Photoshop's eye drag, one for every list with eyes or locks (owner 2026-10-07: «если я зажимаю глаз ... и потом не отпуская тяну вниз
// или вверх мышку, то и другой включается или выключается в зависимости от того, что с initial layer. Так нужно сделать везде»). A press
// on a row's button switches that row; every button of the same kind the pointer then passes over gets the SAME new state (it is set,
// not switched); letting go ends it. The host makes the whole drag one undo step (begin, end). Dragged past the top or the bottom of
// the list's scroll box, the box scrolls that way, faster the farther the pointer is past its edge, and the rows that scroll under the
// pointer get the state too (owner 2026-10-07, about the 3D studio's 18 cameras: «если я вниз тяну за пределы скролла, то оно
// скроллится дальше»). The pointer is captured, so the drag goes on outside the list; the rows under it are found with
// elementFromPoint in the start button's column, so a list that redraws its rows on every change keeps working (WebKit too).
// A press on a row that is one of several chosen rows sets every chosen row too (owner 2026-10-07: «Shift + выбор двух и более объектов,
// и когда потом нажимаю на lock или глаз, то блокирую все выбранные»), as in Figma and Photoshop; a row outside the choice only itself.
//   hyEyeDrag(container, { selector, get(btn) -> bool, set(btn, on), key(btn), can(btn), also(btn, on, done) -> count, begin(on), end(count) })
// selector: the buttons of one kind ([data-a=eye]); get: the state of a button's thing now; set: give it a state; key: who the thing is
// (a row's id; the button itself when the list keeps its rows); can: false leaves a press to the host; also: at the press, the host sets
// the other chosen rows of the pressed one to the same state, adds their keys to done (a Set) and returns how many changed; begin before the first change, end after the last (count: how many
// things changed). The click that follows a press is swallowed, so a host keeps its click handler for the keys (Enter, Space) alone.
// Used by the frame editor's Layers (eyes and locks), the Raw Editor's section eyes (hyimg-frames editor/colorgrade.js) and the 3D
// studio's outliner (eyes and locks of objects, lights and cameras, hyimg-3d-studio engine.js).
(() => {
  if (window.hyEyeDrag) return;
  const st = document.createElement("style");
  st.textContent = ":root.hy-eyedrag, :root.hy-eyedrag * { cursor: default !important; user-select: none !important; -webkit-user-select: none !important; }";
  (document.head || document.documentElement).appendChild(st);
  // the box that scrolls the list: the nearest ancestor that can scroll up or down (inside the container, or the panel around it)
  const scroller = el => {
    for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
      const oy = getComputedStyle(e).overflowY;
      if ((oy === "auto" || oy === "scroll") && e.scrollHeight > e.clientHeight + 1) return e;
    }
    return null;
  };
  window.hyEyeDrag = (container, o) => {
    const key = o.key || (b => b);
    let d = null;
    const hit = (x, y) => { const el = document.elementFromPoint(x, y), b = el && el.closest && el.closest(o.selector); return b && container.contains(b) ? b : null; };
    const touch = b => {
      if (!b || !d) return; const k = key(b); if (d.done.has(k)) return; d.done.add(k);
      if (!!o.get(b) === d.on) return;
      o.set(b, d.on); d.count++;
    };
    // every point between the last one and this one, a few px apart, in the start button's column (a fast drag skips no row)
    const sweep = (y) => {
      const y0 = d.y, n = Math.max(1, Math.ceil(Math.abs(y - y0) / 4));
      for (let i = 1; i <= n; i++) touch(hit(d.x, y0 + (y - y0) * i / n));
      d.y = y;
    };
    const tick = () => {
      if (!d) return; d.raf = 0;
      const s = d.box; if (!s) return;
      const r = s.getBoundingClientRect(), y = d.py;
      const past = y < r.top ? y - r.top : y > r.bottom ? y - r.bottom : 0;
      if (!past) return;
      const was = s.scrollTop;
      s.scrollTop += Math.sign(past) * Math.min(18, 2 + Math.abs(past) * 0.25);   // at most 18 px a frame: the shortest row is longer, none slips by
      if (s.scrollTop !== was) {
        // the rows that came under the box's edge, where the pointer left it
        const edge = past > 0 ? r.bottom - 2 : r.top + 2; d.y = edge - (s.scrollTop - was); sweep(edge);
      }
      d.raf = requestAnimationFrame(tick);
    };
    const stop = () => {
      if (!d) return; const was = d; d = null;
      if (was.raf) cancelAnimationFrame(was.raf);
      document.documentElement.classList.remove("hy-eyedrag");
      try { container.releasePointerCapture(was.pid); } catch (e) {}
      // the click this press makes is the drag's, not a second switch
      const eat = e => { e.stopPropagation(); e.preventDefault(); };
      window.addEventListener("click", eat, { capture: true, once: true });
      setTimeout(() => window.removeEventListener("click", eat, { capture: true }), 0);
      if (o.end) o.end(was.count);
    };
    container.addEventListener("pointerdown", e => {
      if (e.button !== 0 || d) return;
      const b = e.target.closest && e.target.closest(o.selector); if (!b || !container.contains(b)) return;
      if (o.can && !o.can(b)) return;
      e.preventDefault(); e.stopPropagation();
      const r = b.getBoundingClientRect();
      d = { on: !o.get(b), done: new Set(), count: 0, x: r.left + r.width / 2, y: e.clientY, py: e.clientY, pid: e.pointerId, box: scroller(b), raf: 0 };
      try { container.setPointerCapture(e.pointerId); } catch (er) {}
      document.documentElement.classList.add("hy-eyedrag");
      if (o.begin) o.begin(d.on);
      touch(b);
      if (o.also) d.count += o.also(b, d.on, d.done) || 0;
    }, true);
    container.addEventListener("pointermove", e => {
      if (!d || e.pointerId !== d.pid) return;
      d.py = e.clientY;
      const s = d.box, r = s && s.getBoundingClientRect();
      sweep(r ? Math.max(r.top + 2, Math.min(r.bottom - 2, e.clientY)) : e.clientY);
      if (r && (e.clientY < r.top || e.clientY > r.bottom)) {
        touch(hit(d.x, e.clientY));   // past the box, over the next list of the same panel (the 3D studio's sections): its row too
        if (!d.raf) d.raf = requestAnimationFrame(tick);
      }
    });
    container.addEventListener("pointerup", stop); container.addEventListener("pointercancel", stop); container.addEventListener("lostpointercapture", stop);
    return { get active() { return !!d; } };
  };
})();
