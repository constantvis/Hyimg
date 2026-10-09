// The window is dragged by the empty part of its top band (owner 2026-10-04: «what the buttons don't cover up top should drag the
// window in macOS; the buttons may change, so they sit above the drag area»). The page in front tells the app where in that band its
// own controls are, the app drags the window from everywhere else (native/Chrome.swift DragStrip).
// The controls are not listed anywhere: whatever the page lays on its background there (a plate, a button, the library) keeps its
// clicks, a button added later included. Each page names its background in window.HY_DRAG:
//   flat: elements that are background themselves, while what lies on them is not (body, the stage, a header bar)
//   deep: elements that are background with everything inside them (the board's world: pictures under the band drag the window too)
// Runs in the top page only and looks into its same-origin frames (the board's canvas inside v2), and only inside the app.
(() => {
  if (window.top !== window) return;
  const wk = (() => { try { return window.webkit.messageHandlers.hyimg; } catch { return null; } })(), cef = /HyimgCEF/.test(navigator.userAgent);
  if (!wk && !cef) return;
  const send = m => { if (wk) wk.postMessage(m); else console.log("HYIMG_MSG:" + JSON.stringify(m)); };
  const BAND = 96, DEFAULT = 52, SKIP = new Set(["SCRIPT", "STYLE", "LINK", "META", "TEMPLATE", "NOSCRIPT"]);
  const cfg = w => { try { return w.HY_DRAG || {}; } catch { return {}; } };
  const flatOf = w => "html, body" + (cfg(w).flat ? ", " + cfg(w).flat : "");
  // the plates: what lies straight on the background (a plate with its buttons, the library), with frames looked into; a few dozen
  // elements, so a pass costs well under a millisecond (hit testing the band point by point went through the board's thousands of
  // pictures, 60 ms a pass)
  function holesIn(w, ox, oy, out) {
    const flat = flatOf(w), deep = cfg(w).deep;
    for (const bg of w.document.querySelectorAll(flat)) for (const el of bg.children)
      if (!SKIP.has(el.tagName) && !el.matches(flat) && !(deep && el.matches(deep))) plate(el, w, ox, oy, out);
  }
  function plate(el, w, ox, oy, out) {
    const r = el.getBoundingClientRect();
    // a box with no size of its own holding fixed plates (a Studio's root: Dev Studio's .dvui with its Done, Reload and Open in the top
    // row) lays nothing itself, its children may: they are looked at, else the window dragged under them and ate their clicks (owner
    // 2026-10-09 in Dev Studio: «ты не можешь ничего нажать ... Кнопки не работают вообще»); one not drawn (display: none) holds none
    if ((r.width < 4 || r.height < 4) && (el.getClientRects().length || w.getComputedStyle(el).display === "contents")) {
      for (const c of el.children) if (!SKIP.has(c.tagName)) plate(c, w, ox, oy, out);
      return;
    }
    if (r.width < 4 || r.height < 4 || r.top + oy >= BAND || r.bottom + oy <= 0) return;   // nothing of it in the band
    if (el.tagName === "IFRAME") {
      try { const cw = el.contentWindow; if (cw && cw.document.documentElement) { watch(cw); holesIn(cw, ox + r.left + el.clientLeft, oy + r.top + el.clientTop, out); return; } } catch {}
    }
    const s = w.getComputedStyle(el);
    if (s.visibility === "hidden" || +s.opacity === 0) return;   // there but not seen yet (the board's controls before they come in)
    for (let e = el.parentElement; e && e !== w.document.documentElement; e = e.parentElement) if (+w.getComputedStyle(e).opacity === 0) return;
    if (s.pointerEvents === "none") { for (const c of el.children) plate(c, w, ox, oy, out); return; }   // clicks go through it, not through what it holds
    const x0 = Math.max(0, Math.floor(r.left + ox)), y0 = Math.max(0, Math.floor(r.top + oy));
    out.push([x0, y0, Math.ceil(Math.min(innerWidth, r.right + ox)) - x0, Math.ceil(r.bottom + oy) - y0]);
  }
  let last = "";
  function scan() {
    const holes = []; holesIn(window, 0, 0, holes);
    // the band reaches just under the plates along the top (owner's drawing), whatever tall panel also starts there
    const tops = holes.filter(h => h[1] < 40 && h[1] + h[3] < 90).map(h => h[1] + h[3]);
    const h = tops.length ? Math.min(96, Math.max(...tops) + 6) : DEFAULT;
    const m = { action: "dragband", h, holes: holes.map(r => [r[0], r[1], r[2], Math.min(r[3], h - r[1])]).filter(r => r[3] > 0) };
    const k = JSON.stringify(m);
    if (k !== last) { last = k; send(m); }
  }
  // never in the middle of the owner's work: a pass reads styles, which costs a frame while the board moves, so it waits until the
  // pointer and the wheel have rested half a second (the board's pan and zoom, a drag of pictures)
  let t = 0, busyUntil = 0;
  const kick = (ms = 120) => { clearTimeout(t); t = setTimeout(() => { if (document.hidden) return; if (performance.now() < busyUntil) return kick(300); scan(); }, ms); };
  const busy = () => { busyUntil = performance.now() + 500; };
  function watch(w) {
    if (w.__hyDrag) return; w.__hyDrag = true;
    // the controls move when the page lays itself out again, ends an animation (the board's entrance) or after a click or a key
    for (const ev of ["animationend", "transitionend"]) w.addEventListener(ev, () => kick(), true);
    for (const ev of ["pointerup", "keyup"]) w.addEventListener(ev, () => kick(350), true);
    for (const ev of ["wheel", "pointermove", "pointerdown"]) w.addEventListener(ev, busy, { capture: true, passive: true });
    w.addEventListener("resize", () => kick());
  }
  watch(window);
  addEventListener("message", () => kick(250));
  document.addEventListener("visibilitychange", () => kick());
  if (document.readyState === "complete") kick(); else addEventListener("load", () => kick());
  setInterval(() => kick(0), 2000);   // a safety net for changes no event announces
  window.hyDragScan = scan;
})();
