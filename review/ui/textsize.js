// The five text sizes of a text and a timeline's labels, kept in the text's own scale (owner 2026-10-10: «text: при переключении с H1
// или H2, и вот уменьшение-увеличение текста, какая-то просто колоссальнейшая разница в размерах. Что-то там не так ты посчитал»).
// canvas.html TSIZE is the ladder in board units. A text made zoomed in is made smaller, as big on screen as at 100 % (ui/newsize.js,
// 2026-10-07): at 400 % a new text was fs 10, and H2, H1 and the two A's then jumped to the ladder's absolute sizes, 128 and 874, 13 and
// 87 times bigger. Now a text keeps that factor as its scale k (only when under 1) and every size of the ladder is TSIZE[i].fs × k: H1,
// H2, the small and big A, the size lit on its bar and its name. A text made before k: its scale is read once from fs / TSIZE[size].fs
// when that is under 1, then kept on the next size it gets. A text scaled by its corner keeps k and lights no size, as before.
//   hyTextSize.k(t)          the text's scale (1 for most)
//   hyTextSize.make(size, z) { fs, size, k? } for a new text or timeline at this zoom (k only when under 1)
//   hyTextSize.cur(t)        the index of its size on the ladder, -1 when it has none of the five (scaled by the corner)
//   hyTextSize.near(t)       the nearest size on its ladder
//   hyTextSize.set(t, i)     that size (a document's width with it); step(t, d) one size down (-1) or up (1) from its own
(() => {
  if (window.hyTextSize) return;
  const L = () => TSIZE;   // canvas.html, read at call time
  function k(t) {
    if (t && t.k > 0) return t.k;
    const z = t && Number.isInteger(t.size) && L()[t.size], r = z && t.fs / z.fs;
    return r && r < 0.98 ? r : 1;   // a text made zoomed in before k was kept
  }
  const fsAt = (i, kk) => L()[i].fs * kk;
  function cur(t) { const kk = k(t); return L().findIndex((z, i) => Math.abs(fsAt(i, kk) - t.fs) < Math.max(.01, .5 * kk)); }
  function near(t) {
    const kk = k(t), c = cur(t); if (c >= 0) return c;
    return L().reduce((b, z, i) => Math.abs(Math.log(t.fs / fsAt(i, kk))) < Math.abs(Math.log(t.fs / fsAt(b, kk))) ? i : b, 0);
  }
  function set(t, i) {
    const kk = k(t), fs = fsAt(i, kk);
    if (kk !== 1) t.k = kk;
    if (t.tw) t.tw *= fs / t.fs;   // a document: its width too
    t.size = i; t.fs = fs;
  }
  function step(t, d) {
    const kk = k(t), c = cur(t), at = near(t), n = L().length;
    const to = c >= 0 ? at + d : (d < 0 ? (fsAt(at, kk) < t.fs ? at : at - 1) : (fsAt(at, kk) > t.fs ? at : at + 1));
    set(t, Math.max(0, Math.min(n - 1, to)));
  }
  function make(size, zoom) {
    const kk = hyNewSize.text(zoom), out = { fs: L()[size].fs * kk, size };
    if (kk < 1) out.k = kk;
    return out;
  }
  window.hyTextSize = { k, cur, near, set, step, make };
})();
