// The library keeps the picture you are looking at in its place when its width changes (owner 2026-10-06: «I make it wider or narrower
// and the picture at the top flies away, the whole position changes; Apple's gallery keeps you where you look, and the content above
// and below adapts»). Narrower or wider, the cards reflow into other rows and every row above the one in view changes height, so the
// same scroll offset shows other pictures. Here the card at the top left of the view is the anchor: its path and its distance from the
// view's top are noted on every scroll; when the list changes size (the grip, full width, the window, the batches' placeholder heights
// settling 160 ms later) the scroll moves so that card is back at that distance. The page's cards are <button class="card" data-i>
// over its list `view` (v2.html); the list scrolls in <main> beside the canvas and in the document alone.
(() => {
  if (window.hyLibAnchor) return;
  const list = document.getElementById("list"); if (!list) return;
  const box = () => document.body.classList.contains("cv-on") ? document.querySelector("main") : document.scrollingElement;
  const top = b => b === document.scrollingElement ? 0 : b.getBoundingClientRect().top;
  const left = b => b === document.scrollingElement ? 0 : b.getBoundingClientRect().left;
  const pathOf = c => { try { return (view[+c.dataset.i] || {}).path; } catch { return null; } };
  const cardOf = path => { let k = -1; try { k = view.findIndex(i => i.path === path); } catch {} return k < 0 ? null : list.querySelector(`.card[data-i="${k}"]`); };
  let anchor = null, expect = null, raf = 0, until = 0;
  list.style.overflowAnchor = "none";   // the engine's own scroll anchoring would move it a second time
  // the first card whose bottom is below the view's top band (the path bar lies over the first 60 px beside the canvas)
  function note() {
    const b = box(); if (!b) return;
    const g = list.querySelector(".grid"), band = top(b) + (b === document.scrollingElement ? 80 : 64);
    const x = (g ? g.getBoundingClientRect().left : left(b)) + 12;   // the cards' first column (the folders may lie over the list's left part)
    let el = null;
    for (const dy of [6, 40, 90, 150]) { const e = document.elementFromPoint(x, band + dy), c = e && e.closest && e.closest("#list .card[data-i]"); if (c) { el = c; break; } }
    if (!el) return;   // a heading or a gap under the band: the last anchor stays
    const p = pathOf(el); if (p) anchor = { path: p, off: el.getBoundingClientRect().top - top(b) };
  }
  function hold() {
    const b = box(); if (!anchor || !b) return;
    const c = cardOf(anchor.path); if (!c) return;
    const d = c.getBoundingClientRect().top - top(b) - anchor.off; if (Math.abs(d) < 1) return;
    expect = b.scrollTop + d; b.scrollTop = expect;
  }
  const onScroll = () => {
    const b = box(); if (!b) return;
    if (expect != null && Math.abs(b.scrollTop - expect) < 2) { expect = null; return; }   // our own move: the anchor stays
    if (performance.now() < until) return;   // the reflow's own scroll while the width changes: the anchor stays
    expect = null; if (!raf) raf = requestAnimationFrame(() => { raf = 0; note(); });
  };
  addEventListener("scroll", onScroll, { passive: true, capture: true });
  // a width change, and for 450 ms after the last one (the batches' placeholder heights settle 160 ms after it, sizeGrids): the anchor is
  // held every frame. Only then: a new filter or folder draws the list again from its top, that is not held
  let w = list.clientWidth, loop = 0;
  const tick = () => { hold(); loop = performance.now() < until ? requestAnimationFrame(tick) : 0; };
  new ResizeObserver(() => {
    if (list.clientWidth === w) return;
    w = list.clientWidth; until = performance.now() + 450; hold(); if (!loop) loop = requestAnimationFrame(tick);
  }).observe(list);
  window.hyLibAnchor = { note, hold, get anchor() { return anchor; } };
})();
