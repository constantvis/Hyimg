// A board coming in through a switch (⌃Tab, the crumb's list of boards: native/Switcher.swift, ui/switcher.js), the canvas's side.
// Owner 2026-10-08, a board woken behind another, right after the switch at 23 %: «вот такой баг при переключении». Its loading list
// («Library: 222 frames, drawing the board», the ring still turning) stayed over the board: the list ends with the entrance (canvas.html
// intro), and a board that comes in through a switch has none. And it came in half empty, the far view's pictures and the HTML cards'
// stills still on their way: the app brought it in as soon as its board was laid out (canvasReady), not drawn.
//   hyimgQuietIn()       the board comes in without the entrance: its loading steps, its plate and its stars end as the entrance ends them
//   hyimgViewDrawn(ms)   a promise, true once what is on its screen is drawn (every picture in the far view's cell or in its card, a plugin
//                        card's own pictures, as an HTML card's still), false after ms; meanwhile it lays out and draws by itself, since
//                        a page waiting behind another may get no frames
//   hyimgSwitchSettled()  the switch's motion is over: the bars over the selection are laid again
// They read canvas.html's own state (intro, STARS, board, cam, sel, LOD, GL, EL, pendingImgs): only canvas.html loads this file.
(() => {
  window.hyimgQuietIn = () => {
    intro.run = {};   // an entrance under way stops where it is (its steps check it)
    stepsDone();
    if (STARS) { STARS.stop(); STARS = null; }
    document.documentElement.classList.remove("preintro", "hy-open");
  };
  // the switch's motion scales the board's world (ui/switcher.js): a bar over the selection laid while the world was smaller stood off it
  // by its share of that scale once the world was its size again (16 px at 23 %), until the camera moved; it is laid again when it ends
  window.hyimgSwitchSettled = () => { if (sel.size) clampBars(); };
  // a bitmap, or a picture that failed: nothing more is coming for it
  const got = v => !!v || v === false;
  // what on the board's screen is not drawn yet: a picture without its cell (WebGL) or bitmap (the 2D far view), a card's thumbnail on its
  // way (pendingImgs: the view and half a screen around), a plugin card's picture not in; the plugins' cards wait for their plugins
  function missing() {
    if (window.hyPlugBoard && !hyPlugBoard.isReady) return 1;
    const r = stageBox(), x0 = cam.x + INSET / cam.z, y0 = cam.y, x1 = cam.x + r.width / cam.z, y1 = cam.y + r.height / cam.z;
    const gl = document.getElementById("world").classList.contains("gl");
    let n = pendingImgs;
    for (const id in board.items) {
      const it = board.items[id];
      if (it.x > x1 || it.x + (it.w || 0) < x0 || it.y > y1 || it.y + itemH(it) < y0) continue;
      if (!it.type) {
        if (!LOD.on || !it.path) continue;   // zoomed in the pictures are cards, counted in pendingImgs
        const k = pgKey(it);
        if (gl ? !got(GL.slot.get(k)) : !got(LOD.bm.get("96:" + k)) && !got(LOD.bm.get("320:" + k))) n++;
      } else {
        const el = EL.get(id); if (!el || el.hidden) continue;
        for (const img of el.querySelectorAll("img[src]")) if (!img.complete) n++;
      }
    }
    return n;
  }
  window.hyimgViewDrawn = (ms = 5000) => new Promise(done => {
    const end = performance.now() + ms;
    const tick = () => {
      try { cull(); lodDraw(); } catch (e) { console.error("switch-in draw", e); }   // the cards on screen ask for their pictures, the far view for its cells
      const n = missing();
      if (!n || performance.now() > end) done(!n); else setTimeout(tick, 100);
    };
    tick();
  });
})();
