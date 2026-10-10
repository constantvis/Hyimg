// The bars over a selection on the board (canvas.html renderHandles: the selection bar, a note's bar, the frame bar and a plugin's
// edit bar), kept where they can be pressed. One function for every bar, run after each drawing of the handles and each move of the
// camera: the bars move with the board without being drawn again, so this only adds the push that keeps them free.
//
// Owner 2026-10-07: «настройки сверху не должны ездить»: a bar stands centred over its selection and moves with it rigidly;
// it is pushed sideways only when it would leave the board's free part, and then only as far as it must. The free part is the board minus what lies
// on it, measured each time: the library's inset; the side panels (the info panel, a plugin editor's panels: [data-hyui] taller than a
// third of the board, [data-hyside]), each only where it is: a panel at the top right narrows the board for a bar at its height, not
// for one far under it; the top row and the dock with a plugin's axes or title as bands; 8 px from each. Up and down the bars of the
// selection move as one: where they stand when that fits, else mirrored to the selection's other side, else pinned to the free part's
// top over the selection; bars marked data-up (the frame bar and a plugin's bar of a card in its editor) never go under the card. A
// selection wholly out of the window takes its bars and its Info card (#info) with it (owner 2026-10-08: a woken board's opacity bar
// stood alone at the top and its Info card at the right with nothing selected in view), they come back with it; one under the library is
// still pushed to the free part's edge.
//   hyBars.free(stage, inset, band)   {l, r, t, b}: the free part; with band {t, b} the side panels count only where they reach it
//   hyBars.clamp(o)                   o: {stage, inset, cam, sel: {l, r, t, b} on screen or null}
(() => {
  const BANDS = "#crumb, #bset, #bhist, #bkeys, #bntf, #dock, #info, [data-hyui], [data-hyside]";
  function free(stage, inset, band) {
    const st = stage.getBoundingClientRect(), f = { l: st.left + inset + 8, r: st.right - 8, t: st.top + 8, b: st.bottom - 8 };
    document.querySelectorAll(BANDS).forEach(e => {
      if (e.closest("#handles") || !e.getClientRects().length) return;
      const cs = getComputedStyle(e); if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) return;
      const r = e.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.right <= st.left || r.left >= st.right || r.bottom <= st.top || r.top >= st.bottom) return;
      if (e.id === "info" || e.hasAttribute("data-hyside") || r.height > st.height * 0.35) {   // a side panel: the side its middle is on
        if (band && (r.bottom + 8 <= band.t || r.top - 8 >= band.b)) return;   // not at the bars' height
        if ((r.left + r.right) / 2 < (st.left + st.right) / 2) f.l = Math.max(f.l, r.right + 8); else f.r = Math.min(f.r, r.left - 8);
      } else if ((r.top + r.bottom) / 2 < (st.top + st.bottom) / 2) f.t = Math.max(f.t, r.bottom + 8);   // a band at the top or the bottom
      else f.b = Math.min(f.b, r.top - 8);
    });
    return f;
  }
  // a bar that grows after it was placed (its slider, a key cap, a font coming in) is placed again: the Studio chip made a bar measured
  // narrow at first lie over the Info card once it had its width (2026-10-10)
  let last = null, watched = [];
  const ro = window.ResizeObserver ? new ResizeObserver(() => { if (last) requestAnimationFrame(() => (typeof clampBars === "function" ? clampBars() : clamp(last))); }) : null;
  function clamp(o) {
    const bars = [...document.querySelectorAll("#handles .tidy")], S = o.sel, st = o.stage.getBoundingClientRect(), info = document.getElementById("info");
    last = o;
    if (ro) { watched = watched.filter(t => t.isConnected || (ro.unobserve(t), false)); bars.forEach(t => { if (!watched.includes(t)) { watched.push(t); ro.observe(t); } }); }
    const out = !!S && (S.r < st.left || S.l > st.right || S.b < st.top || S.t > st.bottom);
    bars.forEach(t => { t.style.translate = ""; t.style.visibility = out ? "hidden" : ""; });
    if (info) info.style.visibility = out ? "hidden" : "";
    const rs = bars.map(t => t.getBoundingClientRect()), ix = bars.map((t, i) => i).filter(i => rs[i].width);
    if (out || !ix.length) return;
    const fv = free(o.stage, o.inset);
    // up and down, all the bars of the selection as one
    const top = Math.min(...ix.map(i => rs[i].top)), bot = Math.max(...ix.map(i => rs[i].bottom));
    const fits = (a, b) => a >= fv.t - 0.5 && b <= fv.b + 0.5;
    let dy = bars.map(() => 0);
    if (!fits(top, bot)) {
      const above = S && bot <= S.t + 1, below = S && top >= S.b - 1, up = bars.some(t => t.dataset.up);
      // mirrored to the other side of the selection: each bar as far from it as it was, the nearer one stays nearer
      const mir = i => above ? S.b + (S.t - rs[i].bottom) : S.t - (rs[i].top - S.b) - rs[i].height;
      const mt = Math.min(...ix.map(mir)), mb = Math.max(...ix.map(i => mir(i) + rs[i].height));
      if (!up && (above || below) && fits(mt, mb)) dy = bars.map((t, i) => rs[i].width ? mir(i) - rs[i].top : 0);
      else dy = bars.map(() => fv.t - top);   // neither side has room: pinned to the free part's top over the selection
    }
    // sideways: the side panels at the bars' height; one centre for the bars of a selection (stacked bars stay on one axis), the
    // selection's own, moved only as far as the widest bar needs to stay free
    const at = d => free(o.stage, o.inset, { t: Math.min(...ix.map(i => rs[i].top + d[i])), b: Math.max(...ix.map(i => rs[i].bottom + d[i])) });
    const wide = Math.max(...ix.map(i => rs[i].width));
    let f = at(dy), room = f.r - f.l;
    // too wide beside a side panel at this height (the Info card; the bar grew with the Studio chip, 2026-10-10): the other side of the
    // selection, else just under the panel, wherever the whole width is free; it never lies over the panel
    if (S && wide > room) {
      const above = bot <= S.t + 1, info = [...document.querySelectorAll("#info, [data-hyside]")].map(e => e.getClientRects().length ? e.getBoundingClientRect() : null)
        .filter(r => r && r.height >= 4 && r.top < bot && r.bottom > top);
      const shifts = [above ? S.b + (S.t - bot) - top : S.t - (top - S.b) - (bot - top) - top, ...info.map(r => r.bottom + 8 - top)];
      for (const d of shifts.sort((a, b) => Math.abs(a) - Math.abs(b))) {
        const dd = bars.map(() => d), g = at(dd);
        if (fits(top + d, bot + d) && g.r - g.l >= wide) { dy = dd; f = g; room = g.r - g.l; break; }
      }
    }
    const mid = !S ? null : wide > room ? f.l + wide / 2 : Math.min(Math.max((S.l + S.r) / 2, f.l + wide / 2), f.r - wide / 2);
    bars.forEach((t, i) => {
      const r = rs[i]; if (!r.width) return;
      const left = mid != null ? mid - r.width / 2 : r.width > room ? f.l : Math.min(Math.max(r.left, f.l), f.r - r.width);
      const dx = left - r.left;
      if (Math.abs(dx) > 0.25 || dy[i]) t.style.translate = `${dx / o.cam.z}px ${dy[i] / o.cam.z}px`;   // in the board's units: the parent is scaled
    });
  }
  window.hyBars = { free, clamp };
})();
