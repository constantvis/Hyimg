// A live page in a card and the board's zoom (owner 2026-10-08: «zoom над живой страницей увеличивает страницу внутри карточки, а я жду,
// что приблизится холст, как с картинкой»; then: some pages have a zoom of their own, a map, a canvas app). The embed pattern of Figma's
// and Miro's iframes:
//  - a pinch, ⌃ or ⌘ with the wheel over the page zoom the board's camera at the pointer, as over a picture; a plain two-finger scroll still
//    scrolls the page
//  - a click inside the page gives it the zoom («entered») and its own pinch works; the plugin says so in words, nothing is
//    drawn on the card; Esc, a click outside the card or leaving the page gives the zoom back to the board
//  - ⌥ held with a pinch sends that one gesture to the page without entering
// A page of the library's own origin (the frames plugin's HTML frame) is watched from here (local: true). A sandboxed page (Dev mode) is
// another origin: its plugin's script inside it sends the gesture over (Dev studio's agent.js) and the plugin hands it to wheel(), which
// takes only finite numbers in range. Either way the board gets an ordinary wheel event on the card, so it zooms by its own rule.
//   const Z = hyFrameZoom.attach(iframe, { card, local, changed(own) })   Z.owns   Z.enter()   Z.release()   Z.wheel({x, y, dx, dy, mode, ctrl, meta})
//   Z.detach()
(() => {
  if (window.hyFrameZoom) return;
  // nothing is drawn on the card for it (owner 2026-10-08: «все равно обводка эта дурацкая вокруг появляется»): the card wears the class
  // hy-page-own as a state only, the plugin says it in words (Dev mode's dock)
  const css = `.hy-pagezoom.hy-page-own { outline: none !important; }`;
  let styled = false;
  const num = (v, lim) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= lim;
  function attach(f, o = {}) {
    if (!styled) { const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st); styled = true; }
    const card = o.card || f.parentElement, ac = new AbortController(), on = { signal: ac.signal };
    let owns = false, doc = null;
    if (card) card.classList.add("hy-pagezoom");
    const set = v => { if (owns === v) return; owns = v; if (card) card.classList.toggle("hy-page-own", v); try { o.changed && o.changed(v); } catch (e) { console.error(e); } };
    // a gesture of the page as a wheel event on the card: the point from the page's viewport into the window (the frame is scaled)
    function wheel(d) {
      if (owns || !d || !num(d.x, 1e5) || !num(d.y, 1e5) || !num(d.dx, 1e4) || !num(d.dy, 1e4) || !f.isConnected) return false;
      const r = f.getBoundingClientRect(), sx = r.width / (f.offsetWidth || r.width || 1), sy = r.height / (f.offsetHeight || r.height || 1);
      f.dispatchEvent(new WheelEvent("wheel", { clientX: r.left + d.x * sx, clientY: r.top + d.y * sy, deltaX: d.dx, deltaY: d.dy,
        deltaMode: [0, 1, 2].includes(d.mode) ? d.mode : 0, ctrlKey: !!d.ctrl, metaKey: !!d.meta, bubbles: true, cancelable: true }));
      return true;
    }
    // a click anywhere outside the page gives the zoom back (a click inside the page never reaches this document)
    addEventListener("pointerdown", e => { if (owns && e.target !== f) set(false); }, { capture: true, ...on });
    // the page of this origin: its gestures read here, before its own listeners; again for each page it loads (the window object stays,
    // its listeners go with the document)
    function hook() {
      let w = null; try { w = f.contentWindow; if (!w || !w.document) return; } catch { return; }
      if (w.document === doc) return; doc = w.document; set(false);
      const opt = { capture: true, passive: false, signal: ac.signal };
      w.addEventListener("wheel", e => {
        if (!(e.ctrlKey || e.metaKey) || e.altKey || owns) return;
        e.preventDefault(); e.stopImmediatePropagation();
        wheel({ x: e.clientX, y: e.clientY, dx: e.deltaX, dy: e.deltaY, mode: e.deltaMode, ctrl: e.ctrlKey, meta: e.metaKey });
      }, opt);
      ["gesturestart", "gesturechange", "gestureend"].forEach(t => w.addEventListener(t, e => { if (!e.altKey && !owns) { e.preventDefault(); e.stopImmediatePropagation(); } }, opt));
      w.addEventListener("pointerdown", () => set(true), opt);
      w.addEventListener("keydown", e => { if (e.key === "Escape") set(false); }, opt);
    }
    if (o.local) { f.addEventListener("load", hook, on); hook(); }
    return {
      get owns() { return owns; }, enter: () => set(true), release: () => set(false), wheel,
      detach() { set(false); ac.abort(); if (card) card.classList.remove("hy-pagezoom"); },
    };
  }
  window.hyFrameZoom = { attach };
})();
