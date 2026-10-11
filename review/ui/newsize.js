// The size of a new note, heading or timeline follows the zoom (owner 2026-10-07: «размер ноутс зависел от текущего зума ... Текущий
// размер сделай максимальным, а в зависимости от зума адаптируй, чтобы при появлении она была, например, 25% от высоты экрана»).
// Things are made in board units, so zoomed in a picture-sized note covered the screen and had to be made smaller by hand.
// A note's type is a share of its width (canvas.html NSIZE), so a smaller note is the same note, smaller.
(() => {
  // a new note is this share of the board's visible height on screen (it is square, so its width too)
  const NOTE_VIEW_SHARE = 0.25;
  // never under this many screen pixels (a short window), unless the maximum is smaller still (zoomed far out)
  const NOTE_MIN_PX = 160;
  // a new timeline at most this share of the board's free width; a field brought into view stands this far inside the free part
  const LINE_VIEW_SHARE = 0.8, REVEAL_PX = 24;
  window.hyNewSize = {
    NOTE_VIEW_SHARE, NOTE_MIN_PX,
    // a new note's width in board units: the share of the visible height at this zoom, at most `max` (a picture's width on this board,
    // the size every new note had before), so zoomed far out it is no bigger than it always was
    note(max, zoom, viewH) { const px = Math.max(NOTE_MIN_PX, viewH * NOTE_VIEW_SHARE); return Math.max(1, Math.round(Math.min(max, px / zoom))); },
    // a new heading's or timeline's factor on its size: zoomed in it is as big on screen as at 100 %, never bigger
    text(zoom) { return Math.min(1, 1 / zoom); },
    // a new timeline's length in board units: at most this share of the board's free width on screen (board audit 2026-10-11, B-11: at
    // 90 % it was 2333 px on a board 1100 px wide, two of its four dots in view and its first label typed into off screen)
    LINE_VIEW_SHARE,
    line(len, zoom) { const f = window.hyBars ? hyBars.free(stage, INSET) : null; return Math.round(f ? Math.min(len, (f.r - f.l) * LINE_VIEW_SHARE / zoom) : len); },
    // the field of a thing just made (a group's title, a timeline's first label, a note above its picture) opens where it shows (B-09,
    // B-11): the board moves only as far as it must to bring the element into its free part, REVEAL_PX inside its edges; true if it moved
    reveal(el) {
      if (!el || !window.hyBars || typeof cam === "undefined") return false;
      const r = el.getBoundingClientRect(), f = hyBars.free(stage, INSET), m = REVEAL_PX;
      const d = (a, b, lo, hi) => (b - a > hi - lo - 2 * m || a < lo + m ? a - lo - m : b > hi - m ? b - hi + m : 0);
      const dx = d(r.left, r.right, f.l, f.r), dy = d(r.top, r.bottom, f.t, f.b); if (!dx && !dy) return false;
      cam.x += dx / cam.z; cam.y += dy / cam.z; renderCam(); return true;
    },
  };
})();
