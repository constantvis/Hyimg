// The size of a new note, heading or timeline follows the zoom (owner 2026-10-07: «размер ноутс зависел от текущего зума ... Текущий
// размер сделай максимальным, а в зависимости от зума адаптируй, чтобы при появлении она была, например, 25% от высоты экрана»).
// Things are made in board units, so zoomed in a picture-sized note covered the screen and had to be made smaller by hand.
// A note's type is a share of its width (canvas.html NSIZE), so a smaller note is the same note, smaller.
(() => {
  // a new note is this share of the board's visible height on screen (it is square, so its width too)
  const NOTE_VIEW_SHARE = 0.25;
  // never under this many screen pixels (a short window), unless the maximum is smaller still (zoomed far out)
  const NOTE_MIN_PX = 160;
  window.hyNewSize = {
    NOTE_VIEW_SHARE, NOTE_MIN_PX,
    // a new note's width in board units: the share of the visible height at this zoom, at most `max` (a picture's width on this board,
    // the size every new note had before), so zoomed far out it is no bigger than it always was
    note(max, zoom, viewH) { const px = Math.max(NOTE_MIN_PX, viewH * NOTE_VIEW_SHARE); return Math.max(1, Math.round(Math.min(max, px / zoom))); },
    // a new heading's or timeline's factor on its size: zoomed in it is as big on screen as at 100 %, never bigger
    text(zoom) { return Math.min(1, 1 / zoom); },
  };
})();
