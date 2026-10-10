// A live page in a card and the board's zoom (owner 2026-10-08: «zoom над живой страницей увеличивает страницу внутри карточки, а я жду,
// что приблизится холст, как с картинкой»). The embed pattern of Figma's and Miro's iframes:
//  - a pinch, ⌃ or ⌘ with the wheel over the page zoom the board's camera at the pointer, as over a picture; a plain two-finger scroll still
//    scrolls the page
//  - ⌥ held with a pinch sends that one gesture to the page (a map, a canvas app with a zoom of its own); a page that does not take it
//    (no preventDefault) hands it to the board too
//  - nothing ever zooms the window: a pinch nobody took inside a frame was Chromium's pinch-zoom of the whole app, the board, its menus and
//    panels past the window's edges (owner 2026-10-10: «приближается вообще вся наша картинка, и менюшки уходят за границы»)
// Until 2026-10-10 a click inside the page gave it the zoom («The page has the zoom · Esc to give it back»). The owner, the same day: «постоянно
// вот эта вот проблема возникает и препятствует тому, чтобы я нормально пользовался комбинациями кнопок»: every click into a live page
// took the pinch from the board, and a page without a zoom of its own then zoomed the window. That state is gone, ⌥ is the way to the page.
// A page of the library's own origin (the frames plugin's HTML frame) is watched from here (local: true). A sandboxed page (Dev mode) is
// another origin: its plugin's script inside it sends the gesture over (Dev studio's agent.js) and the plugin hands it to wheel(), which
// takes only finite numbers in range. Either way the board gets an ordinary wheel event on the card, so it zooms by its own rule.
//   const Z = hyFrameZoom.attach(iframe, { local })   Z.wheel({x, y, dx, dy, mode, ctrl, meta})   Z.detach()
//   Z.owns (always false), Z.enter(), Z.release(): kept for plugins written before 2026-10-10, they do nothing
(() => {
  if (window.hyFrameZoom) return;
  const num = (v, lim) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= lim;
  const gesture = e => ({ x: e.clientX, y: e.clientY, dx: e.deltaX, dy: e.deltaY, mode: e.deltaMode, ctrl: e.ctrlKey, meta: e.metaKey });
  function attach(f, o = {}) {
    const ac = new AbortController();
    let doc = null;
    // a gesture of the page as a wheel event on the card: the point from the page's viewport into the window (the frame is scaled)
    function wheel(d) {
      if (!d || !num(d.x, 1e5) || !num(d.y, 1e5) || !num(d.dx, 1e4) || !num(d.dy, 1e4) || !f.isConnected) return false;
      const r = f.getBoundingClientRect(), sx = r.width / (f.offsetWidth || r.width || 1), sy = r.height / (f.offsetHeight || r.height || 1);
      f.dispatchEvent(new WheelEvent("wheel", { clientX: r.left + d.x * sx, clientY: r.top + d.y * sy, deltaX: d.dx, deltaY: d.dy,
        deltaMode: [0, 1, 2].includes(d.mode) ? d.mode : 0, ctrlKey: !!d.ctrl, metaKey: !!d.meta, bubbles: true, cancelable: true }));
      return true;
    }
    // the page of this origin: its gestures read here, before its own listeners; again for each page it loads (the window object stays,
    // its listeners go with the document)
    function hook() {
      let w = null; try { w = f.contentWindow; if (!w || !w.document) return; } catch { return; }
      if (w.document === doc) return; doc = w.document;
      const opt = { capture: true, passive: false, signal: ac.signal };
      let alt = null;   // the ⌥ gesture the page sees now: after all its listeners (the window's bubble, added during the dispatch) the board's
      const last = e => { if (e !== alt) return; alt = null; if (!e.defaultPrevented) { e.preventDefault(); wheel(gesture(e)); } };
      w.addEventListener("wheel", e => {
        if (!(e.ctrlKey || e.metaKey)) return;
        if (e.altKey) { alt = e; w.addEventListener("wheel", last, { once: true, passive: false, signal: ac.signal }); return; }
        e.preventDefault(); e.stopImmediatePropagation(); wheel(gesture(e));
      }, opt);
      ["gesturestart", "gesturechange", "gestureend"].forEach(t => w.addEventListener(t, e => { if (!e.altKey) { e.preventDefault(); e.stopImmediatePropagation(); } }, opt));
    }
    if (o.local) { f.addEventListener("load", hook, { signal: ac.signal }); hook(); }
    return {
      owns: false, enter() {}, release() {}, wheel,
      detach() { ac.abort(); },
    };
  }
  window.hyFrameZoom = { attach };
})();
