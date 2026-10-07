// The hover turn of a 3D file's picture (owner 2026-10-06: «on hover it automatically spins 360° around its own axis», in the library's
// 3D filter and in the 3D card's recent list). Not a WebGL context per tile (a browser allows about 16): the file has a turntable sheet,
// N views of it around the vertical axis laid in a grid, drawn once by a page with three.js and kept by the server (server.py
// /api/sprite). At rest the tile shows the first view as an ordinary still picture; while the pointer is over it the sheet is loaded
// and its views are stepped by a clock, a turn in PERIOD ms, which costs one style write per view. On leave the turn finishes at the
// rest view at three times the speed instead of snapping, and stops.
//
// Markup: a host (the tile the pointer enters) holding an element with data-spin='{"sheet": url, "n": 36, "cols": 6}' whose own
// background is the still picture (background-size: cover). hySpin.bind(root, ".host") listens once for all the hosts inside root, also
// the ones drawn later.
(() => {
  if (window.hySpin) return;
  const PERIOD = 3000, SETTLE = 3;
  const sheets = new Map();   // url -> Promise<url> once the browser has decoded it (a hover only waits for the first look at a file)
  const load = url => { if (!sheets.has(url)) { const im = new Image(); im.src = url; sheets.set(url, im.decode().then(() => url, () => { sheets.delete(url); return null; })); } return sheets.get(url); };
  const spec = el => { try { return JSON.parse(el.dataset.spin || "null"); } catch { return null; } };

  function put(el, sp, k) {   // view k of the sheet
    const cols = sp.cols, rows = Math.ceil(sp.n / cols), c = k % cols, r = Math.floor(k / cols);
    el.style.backgroundSize = `${cols * 100}% ${rows * 100}%`;
    el.style.backgroundPosition = `${cols > 1 ? c / (cols - 1) * 100 : 0}% ${rows > 1 ? r / (rows - 1) * 100 : 0}%`;
    el.dataset.view = k;
  }
  function rest(st) {   // the still picture again
    const el = st.el; el.style.backgroundImage = st.was.image; el.style.backgroundSize = st.was.size; el.style.backgroundPosition = st.was.pos;
    el.dataset.view = 0; el.classList.remove("spinning"); st.on = false;
  }
  function start(host) {
    const el = host.querySelector("[data-spin]"), sp = el && spec(el); if (!sp || !sp.sheet || !(sp.n > 1)) return;
    let st = host._spin;
    if (!st) st = host._spin = { el, sp, k: 0, raf: 0, t0: 0, hover: false, on: false, was: null };
    st.hover = true;
    if (st.on) { cancelAnimationFrame(st.raf); st.t0 = performance.now() - st.k * PERIOD / sp.n; st.settle = false; st.raf = requestAnimationFrame(step(st)); return; }   // came back while it was settling
    load(sp.sheet).then(url => {
      if (!url || !st.hover || st.on) return;
      st.on = true; st.settle = false;
      st.was = { image: el.style.backgroundImage, size: el.style.backgroundSize, pos: el.style.backgroundPosition };
      el.style.backgroundImage = `url("${url}")`; el.classList.add("spinning"); put(el, sp, 0); st.k = 0; st.t0 = performance.now();
      st.raf = requestAnimationFrame(step(st));
    });
  }
  const step = st => function frame(now) {
    const n = st.sp.n, per = PERIOD / n;
    if (!st.settle) {
      const k = Math.floor((now - st.t0) / per) % n;
      if (k !== st.k) { st.k = k; put(st.el, st.sp, k); }
    } else {   // on leave: on to the rest view, quicker than the turn, then the still
      const k = Math.floor((now - st.t1) / (per / SETTLE)) + st.k0;
      if (k >= n) { st.k = 0; return rest(st); }
      if (k !== st.k) { st.k = k; put(st.el, st.sp, k); }
    }
    st.raf = requestAnimationFrame(frame);
  };
  function stop(host) {
    const st = host._spin; if (!st) return;
    st.hover = false;
    if (!st.on) return;
    cancelAnimationFrame(st.raf);
    if (st.k === 0) return rest(st);
    st.settle = true; st.k0 = st.k; st.t1 = performance.now(); st.raf = requestAnimationFrame(step(st));
  }

  window.hySpin = {
    PERIOD,
    // the turn of the hosts under root: root.querySelectorAll(hostSel), also later ones
    bind(root, hostSel) {
      const host = e => e.target.closest && e.target.closest(hostSel);
      root.addEventListener("pointerover", e => { const h = host(e); if (h && e.pointerType !== "touch" && !(h.contains(e.relatedTarget))) start(h); });
      root.addEventListener("pointerout", e => { const h = host(e); if (h && !(h.contains(e.relatedTarget))) stop(h); });
    },
    // fetch the sheet before the pointer arrives (the library does it for the tile under the pointer's way)
    preload(sp) { if (sp && sp.sheet) load(sp.sheet); },
  };
})();
