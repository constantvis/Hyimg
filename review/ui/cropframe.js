// The crop of a picture on the board: the frame, its handles, the ratio bar and the crop's own undo steps (moved out of canvas.html
// 2026-10-11 with the board audit's crop fixes, B-01 … B-06, B-08; the owner 2026-10-10 on the crop with its ratio pills: «все прыгает,
// скачет»). canvas.html keeps what touches the rest of the board: applyCrop (the card takes its new crop, one board step), endCrop and the
// trim of a video under its crop. A classic script: canvas.html calls these by name, as it did when they were its own.
//
//   startCrop(id)        open the crop of a picture, a video (crop & trim), a PDF's page
//   drawCrop()           the frame, its eight handles and the bar after any change; the dock's Undo and Redo follow the crop's steps
//   cropDown(e), cropMove(e), cropUp(e)   the pointer on the crop (canvas.html's stage handlers pass it here while cropState is set)
//   cropRatio(k)         "free" | "1:1" … | "flip" (X): the biggest frame of that ratio inside the picture, centred where the frame was
//   cropReset()          R, a double click: the whole picture, or the biggest piece in the locked ratio
//   cropKeep()           a step of the crop begins (the state before it goes on the crop's undo list)
//   cropStep(dir)        -1 undo, 1 redo, of the crop's own steps: ⌘Z, ⇧⌘Z and the dock's Undo and Redo alike (B-06)
//   CROP_RATIOS, RATIO_NAMES, ratioInner(k), ratioAttrs(k)   the ratios, also on the frame bar of a plugin card in its editor
//   The bar ends in Cancel and Done ↵ (round 20, 2026-10-11): the same as Esc and ↵
//
// What the audit of 2026-10-11 found and how it is now:
// - B-01 a ratio under the pointer widened to show its platform («Instagram post», owner 2026-10-06) and the centred bar moved every pill
//   under the hand by up to 50 px. The pills keep their width now; the name shows on a plate over the pill, as the dock's step name
//   over Undo (owner 2026-10-10: «по наведению, чтобы оно изначально не расширяло этот элемент»).
// - B-02 a ratio kept the frame's area, so every pick shrank it. A ratio (and the turn) gives the biggest frame of that ratio inside the
//   picture, centred on the frame's centre and moved in where it would leave the picture, as Lightroom and Photoshop do.
// - B-03 a corner with a locked ratio followed the axis the pointer moved further on and jumped 110 px when that axis changed. The pointer
//   is projected onto the corner's diagonal in the picture's pixels: the size changes smoothly.
// - B-04 a drag inside a frame not cropped yet drew a new frame from the press point. Inside the frame a drag always moves it; a new frame
//   is drawn with ⇧ or from the dim part of the picture outside the frame.
// - B-05 the bar stands over the whole picture (owner 2026-10-06, «the bar jumps around»: it does not follow the frame) and goes through
//   ui/bars.js like every bar over a selection: in the board's free part, never under the dock, back in view after a scroll.
// - B-06 the dock's Undo took a board step under an open crop. Undo and Redo, keys and buttons, are the crop's own steps while it is open.
// - B-08 the corner handles lay inside the clipped window, three quarters of each cut off and dead to the cursor. Eight handles (corners
//   and edges) lie on their own layer over the window, whole.
(() => {
  if (window.drawCrop) return;
  const CSS = `
#crop { position: absolute; display: none; z-index: 20; --crop-edge: #fff; --crop-shade: rgba(0,0,0,.5); --crop-h: #fff; --crop-h-line: #111; }
:root[data-in-studio] #crop { display: none !important; }
#crop img { position: absolute; left: 0; top: 0; width: 100%; height: 100%; opacity: .35; pointer-events: none; }
#crop .win { position: absolute; overflow: hidden; outline: calc(2px / var(--z)) solid var(--crop-edge); box-shadow: 0 0 0 calc(1px / var(--z)) var(--crop-shade); cursor: move; }
#crop .win img { opacity: 1; }
#crop .hs { position: absolute; pointer-events: none; }
#crop .h { background: var(--crop-h); border-color: var(--crop-h-line); margin: 0; scale: none; pointer-events: auto; }
#crop .h[data-c=nw] { left: 0; top: 0; transform: translate(-50%, -50%); cursor: nwse-resize; }
#crop .h[data-c=ne] { right: 0; top: 0; transform: translate(50%, -50%); cursor: nesw-resize; }
#crop .h[data-c=sw] { left: 0; bottom: 0; transform: translate(-50%, 50%); cursor: nesw-resize; }
#crop .h[data-c=se] { right: 0; bottom: 0; transform: translate(50%, 50%); cursor: nwse-resize; }
#crop .h[data-c=n] { left: 50%; top: 0; transform: translate(-50%, -50%); cursor: ns-resize; }
#crop .h[data-c=s] { left: 50%; bottom: 0; transform: translate(-50%, 50%); cursor: ns-resize; }
#crop .h[data-c=w] { left: 0; top: 50%; transform: translate(-50%, -50%); cursor: ew-resize; }
#crop .h[data-c=e] { right: 0; top: 50%; transform: translate(50%, -50%); cursor: ew-resize; }
/* proportions over the crop frame (owner 2026-10-02): Free by default, a ratio locks the frame to it, the turn button turns it */
.cratio button { padding: 0 10px; gap: 0; font-variant-numeric: tabular-nums; }
.cratio button.on { background: var(--ink); color: var(--panel); }
.cratio .flip { width: 30px; padding: 0; justify-content: center; }
/* the turn button is the frame itself (owner 2026-10-06: «portrait / landscape, it just turns, a rectangle with rounded corners») */
.cratio .flip svg { transition: transform .32s cubic-bezier(.32,.72,0,1); }
.cratio .flip.land svg { transform: rotate(90deg); }
.cratio .flip:disabled { opacity: .3; cursor: default; }
.cratio .flip:disabled:hover { background: transparent; }
/* Cancel quiet, Done the main action in the selection's blue with its key (round 20, crop-b.html) */
.cratio button.cend { padding: 0 13px; color: var(--sub); }
.cratio button.cdone { gap: 6px; padding: 0 8px 0 14px; background: var(--sel); color: var(--hy-on-accent); font-weight: 600; }
.cratio button.cdone:hover { background: color-mix(in srgb, var(--sel) 86%, var(--hy-on-accent)); }
.cratio .cdone hy-kbd { background: color-mix(in srgb, var(--hy-on-accent) 20%, transparent); border-color: transparent; color: var(--hy-on-accent); }
/* which platform a ratio is (owner 2026-10-06), on a plate over the pill under the pointer: the dock's step plate (ui/dock.js #hydkstep);
   the pills and the bar never change their width for it (board audit B-01) */
.cratio .rtip { position: absolute; left: 0; bottom: calc(100% + 6px); translate: -50% 0; display: flex; align-items: center; height: 26px; padding: 0 10px;
  white-space: nowrap; border: 1px solid var(--line); border-radius: 999px; background: color-mix(in srgb, var(--panel) 86%, transparent);
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); box-shadow: var(--plate-sh); color: var(--ink); font: 500 12px var(--sans);
  pointer-events: none; opacity: 0; transition: opacity .16s cubic-bezier(.32,.72,0,1); }
.cratio .rtip.dn { bottom: auto; top: calc(100% + 6px); }
.cratio .rtip.on { opacity: 1; }
:root[data-shape=pro] .cratio .rtip { border-radius: 9px; }
@media (prefers-reduced-motion: reduce) { .cratio .rtip { transition: none; } }`;
  const st = document.createElement("style"); st.id = "hy-crop-css"; st.textContent = CSS; (document.head || document.documentElement).appendChild(st);
  const $ = q => document.querySelector(q);

  // standard proportions, portrait way round; the turn button (or X) turns them (owner 2026-10-02: "1:1 or 3:4 or flip to 4:3, and others").
  // Round 20 (owner 2026-10-11 on the crop: «недостаточность форматов»): 1.91:1 (a link's picture) and 21:9 (cinema) join the five
  const CROP_RATIOS = [[1, 1], [4, 5], [3, 4], [2, 3], [1, 1.91], [9, 16], [9, 21]];
  // which format a ratio is, on the plate over its pill (owner 2026-10-06; every pill has one since 2026-10-11, round 20: «описании при
  // наведении»). Brand names stay as they are in both languages, the plain words go through T (ui/lang-board.js)
  const RATIO_NAMES = { "1:1": "Instagram post", "4:5": "Instagram post", "5:4": "Print 10 × 8", "3:4": "Instagram grid · iPad", "4:3": "iPhone photo · iPad",
    "2:3": "Pinterest", "3:2": "35 mm photo", "1:1.91": "Tall banner", "1.91:1": "Facebook · LinkedIn · X link", "9:16": "Reels · Stories · TikTok · Shorts",
    "16:9": "YouTube", "9:21": "Ultrawide, upright", "21:9": "Cinema · Ultrawide" };
  const PLAIN = new Set(["Print 10 × 8", "Instagram grid · iPad", "iPhone photo · iPad", "35 mm photo", "Tall banner", "Facebook · LinkedIn · X link",
    "Ultrawide, upright", "Cinema · Ultrawide"]);
  const ratioName = k => { const n = RATIO_NAMES[k] || ""; return PLAIN.has(n) ? T(n) : n; };
  const ratioInner = k => `<span class="rk">${k}</span>`;
  const ratioAttrs = k => (RATIO_NAMES[k] ? ` data-n="${ratioName(k)}" aria-label="${k} ${ratioName(k)}"` : "");
  const MIN = 0.03;   // the smallest frame, a share of the picture's side

  // The crop shows only while a crop is open on the board: never in a Studio or a plugin's live view (ui/modes.js data-in-studio; owner
  // 2026-10-11, the ratio bar stood over an HTML frame's live page), and such a session opening calls an open crop off
  const inSession = () => document.documentElement.hasAttribute("data-in-studio");
  new MutationObserver(() => { if (inSession() && typeof cropState !== "undefined" && cropState && typeof endCrop === "function") endCrop(); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-in-studio"] });
  function startCrop(id) {
    const it = board.items[id]; if (!it || inSession()) return;
    if (isVid(it)) { vidHover(null); vidKill(id); }   // its card hides under the crop; the clip plays in the crop window instead
    if (window.hyAnnot && hyAnnot.active) hyAnnot.exit();   // one tool at a time (P4 B-30); before cropState: its exit draws the board
    const c = cropOf(it), fw = it.w / (c[2] - c[0]), fh = fw / it.ar;
    // ratio: null is free, else width:height in pixels; land: the bar shows 4:3 instead of 3:4, as the picture itself stands (B-02)
    cropState = { id, full: { x: it.x - c[0] * fw, y: it.y - c[1] * fh, w: fw, h: fh }, c: [...c], act: null, ratio: null, key: "free", land: fw > fh, undo: [], redo: [] };
    const box = $("#crop"), src = thumbUrl(pgKey(it), 1280), hs = ["nw", "n", "ne", "e", "se", "s", "sw", "w"].map(k => `<span class="h" data-c="${k}"></span>`).join("");
    box.innerHTML = `<img src="${src}" alt=""><div class="win"><img src="${src}" alt=""></div><div class="hs">${hs}</div>`
      + `<div class="tidy cratio"><button data-ratio="free" title="${T("crop::Free frame")}">${T("Free")}</button>`
      + CROP_RATIOS.map(([a, b]) => `<button data-ratio="${a}:${b}">${ratioInner(`${a}:${b}`)}</button>`).join("")
      + `<button class="flip${cropState.land ? " land" : ""}" data-ratio="flip" title="${T("Turn the ratio · X")}">${hyIcon("orientation", 15, 2)}</button>`
      // Cancel and Done, as Photoshop's ✓ and ⦸ (round 20, crop-b.html, board audit B-07): the mouse can leave the crop now; a press beside the
      // picture still does nothing (P4 B-46, 2026-10-10)
      + `<span class="sep"></span><button class="cend" data-cropend="cancel" title="${T("Cancel the crop · Esc")}">${T("Cancel")}</button>`
      + `<button class="cend cdone" data-cropend="done" title="${T("Apply the crop · ↵")}">${T("Done")}<hy-kbd size="s">↵</hy-kbd></button></div>`;
    if (isVid(it)) trimStart(id);
    box.style.display = "block"; drawCrop(); render();
    // its keys in the Hint bar under the top row, the one of every tool (round 20, tips-a.html: «кадрирование берет общую строку подсказок
    // под рядом»; board audit B-19: it had its own #hint line in the top row, all the time); endCrop hides it
    cropState.hint = window.hyHint ? hyHint(isVid(it) ? "crop:trim" : "crop", box) : null;
  }

  function drawCrop() {
    const s = cropState, f = s.full, c = s.c, box = $("#crop"); if (!box.querySelector(".win")) return;
    Object.assign(box.style, { left: f.x + "px", top: f.y + "px", width: f.w + "px", height: f.h + "px" });
    const at = { left: c[0] * f.w + "px", top: c[1] * f.h + "px", width: (c[2] - c[0]) * f.w + "px", height: (c[3] - c[1]) * f.h + "px" };
    Object.assign(box.querySelector(".win").style, at); Object.assign(box.querySelector(".hs").style, at);
    box.querySelectorAll(".win img, .win video").forEach(wi => Object.assign(wi.style, { width: f.w + "px", height: f.h + "px", left: -c[0] * f.w + "px", top: -c[1] * f.h + "px" }));
    // the trim strip lies over the bottom of the whole clip, the ratio bar stands over the whole picture, centred on it (owner 2026-10-06:
    // «the bar jumps around»): neither follows the frame; ui/bars.js keeps the bar in the board's free part (canvas.html clampBars)
    const vt = box.querySelector(".vtrim"); if (vt) Object.assign(vt.style, { left: "0px", top: f.h + "px", width: f.w + "px" });
    const bar = box.querySelector(".cratio");
    if (bar) {
      Object.assign(bar.style, { left: f.w / 2 + "px", top: "0px" });
      bar.querySelectorAll("button[data-ratio]").forEach(b => {
        const k = b.dataset.ratio; if (k === "flip") { b.disabled = s.key === "1:1"; b.classList.toggle("land", s.land); return; }
        if (k !== "free") {
          const [a, d] = k.split(":"), k2 = s.land && a !== d ? `${d}:${a}` : k, nm = ratioName(k2);
          if (b.dataset.k !== k2) {
            b.dataset.k = k2; b.innerHTML = ratioInner(k2);
            if (nm) { b.dataset.n = nm; b.setAttribute("aria-label", `${k2} ${nm}`); } else { delete b.dataset.n; b.removeAttribute("aria-label"); }
          }
        }
        b.classList.toggle("on", k === s.key);
      });
      const tp = bar.querySelector(".rtip.on"), hov = bar.querySelector("button:hover"); if (tp) tip(bar, hov && hov.dataset.n ? hov : null);   // X under the pointer: the new name
    }
    const u = $("#bundo"), r = $("#bredo"); if (u) u.disabled = !s.undo.length; if (r) r.disabled = !s.redo.length;   // the dock follows the crop's steps
  }

  // ---- the platform's name over a ratio pill (B-01): a plate in the bar, so nothing in the bar moves -------------------------------
  function tip(bar, b) {
    let tp = bar.querySelector(":scope > .rtip");
    if (!b) { if (tp) tp.classList.remove("on"); return; }
    if (!tp) { tp = document.createElement("span"); tp.className = "rtip"; tp.setAttribute("aria-hidden", "true"); bar.appendChild(tp); }
    tp.textContent = b.dataset.n; tp.style.left = b.offsetLeft + b.offsetWidth / 2 + "px";
    const r = bar.getBoundingClientRect(), f = window.hyBars ? hyBars.free(stage, INSET) : { t: 0 };
    tp.classList.toggle("dn", r.top - 36 < f.t); tp.classList.add("on");   // no room over the bar (pinned at the top): under it
  }
  addEventListener("pointerover", e => {
    const bar = e.target.closest && e.target.closest(".cratio"); if (!bar) return;
    const b = e.target.closest("button"); tip(bar, b && b.dataset.n ? b : null);
  });
  addEventListener("pointerout", e => {
    const bar = e.target.closest && e.target.closest(".cratio"); if (bar && !(e.relatedTarget && bar.contains(e.relatedTarget))) tip(bar, null);
  });

  // ---- ratios ----------------------------------------------------------------------------------------------------------------------
  function cropFit(r) {   // the biggest frame of ratio r (width:height in pixels) inside the picture, centred on the frame's centre (B-02)
    const s = cropState, c = s.c, rn = r * s.full.h / s.full.w, w = Math.min(1, rn), h = w / rn;
    const cx = Math.min(1 - w / 2, Math.max(w / 2, (c[0] + c[2]) / 2)), cy = Math.min(1 - h / 2, Math.max(h / 2, (c[1] + c[3]) / 2));
    s.c = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
  }
  function cropRatio(k) {
    const s = cropState; if (!s) return;
    if (k === "flip") {   // free: the frame itself turns; a ratio: 3:4 becomes 4:3
      s.land = !s.land;
      if (s.ratio) s.ratio = 1 / s.ratio;
      cropFit(s.ratio || ((s.c[3] - s.c[1]) * s.full.h) / ((s.c[2] - s.c[0]) * s.full.w));
    } else if (k === "free") { s.ratio = null; s.key = "free"; }
    else { const [a, b] = k.split(":").map(Number); s.key = k; s.ratio = s.land ? b / a : a / b; cropFit(s.ratio); }
    drawCrop();
  }
  function cropReset() { const s = cropState; s.c = [0, 0, 1, 1]; s.act = null; if (s.ratio) cropFit(s.ratio); drawCrop(); }   // R, double click
  // a frame locked to a ratio grows from an anchor (the opposite corner, the press point, or the centre with ⌥) toward the pointer, as far
  // as the picture allows. The pointer is projected onto the corner's diagonal (sx, sy / r) in the picture's pixels (B-03: the size
  // followed the axis the pointer moved further on and jumped when that axis changed); w is the frame's width, its half with ⌥
  function ratioRect(ax, ay, sx, sy, n, alt, min) {
    const s = cropState, f = s.full, r = s.ratio, rn = r * f.h / f.w;
    const roomX = alt ? Math.min(ax, 1 - ax) : (sx > 0 ? 1 - ax : ax), roomY = alt ? Math.min(ay, 1 - ay) : (sy > 0 ? 1 - ay : ay);
    const px = (n[0] - ax) * f.w, py = (n[1] - ay) * f.h;
    let w = (px * sx + py * sy / r) / (1 + 1 / (r * r)) / f.w; w = Math.max(min, Math.min(w, roomX, roomY * rn)); const h = w / rn;
    return alt ? [ax - w, ay - h, ax + w, ay + h] : [Math.min(ax, ax + sx * w), Math.min(ay, ay + sy * h), Math.max(ax, ax + sx * w), Math.max(ay, ay + sy * h)];
  }
  // an edge with a locked ratio: the edge follows the pointer, the other side grows with it around the frame's middle (⌥: both edges)
  function ratioEdge(c0, side, n, alt) {
    const s = cropState, rn = s.ratio * s.full.h / s.full.w, cx = (c0[0] + c0[2]) / 2, cy = (c0[1] + c0[3]) / 2, k = alt ? 1 : 2;
    if (side === "e" || side === "w") {
      const sx = side === "e" ? 1 : -1, ax = alt ? cx : (sx > 0 ? c0[0] : c0[2]), room = alt ? Math.min(ax, 1 - ax) : (sx > 0 ? 1 - ax : ax);
      const w = Math.max(MIN / k, Math.min(sx * (n[0] - ax), room, k * Math.min(cy, 1 - cy) * rn)), hh = w / rn / k;
      return alt ? [ax - w, cy - hh, ax + w, cy + hh] : [Math.min(ax, ax + sx * w), cy - hh, Math.max(ax, ax + sx * w), cy + hh];
    }
    const sy = side === "s" ? 1 : -1, ay = alt ? cy : (sy > 0 ? c0[1] : c0[3]), room = alt ? Math.min(ay, 1 - ay) : (sy > 0 ? 1 - ay : ay);
    const h = Math.max(MIN / k, Math.min(sy * (n[1] - ay), room, k * Math.min(cx, 1 - cx) / rn)), hw = h * rn / k;
    return alt ? [cx - hw, ay - h, cx + hw, ay + h] : [cx - hw, Math.min(ay, ay + sy * h), cx + hw, Math.max(ay, ay + sy * h)];
  }

  // ---- the crop's own steps (B-06) ---------------------------------------------------------------------------------------------------
  const state = () => { const s = cropState; return { c: [...s.c], ratio: s.ratio, key: s.key, land: s.land }; };
  function cropKeep() { const s = cropState; s.undo.push(state()); s.redoWas = s.redo; s.redo = []; }
  function cropStep(dir) {
    const s = cropState; if (!s) return false; const from = dir < 0 ? s.undo : s.redo, to = dir < 0 ? s.redo : s.undo; if (!from.length) return false;
    to.push(state()); Object.assign(s, from.pop(), { act: null }); drawCrop();
    if (window.hyBoardDock && hyBoardDock.steps) hyBoardDock.steps.done(dir < 0 ? "undo" : "redo");   // the plate «Undo · Crop frame» for 2 s
    return true;
  }

  // ---- the pointer -------------------------------------------------------------------------------------------------------------------
  const normOf = p => { const f = cropState.full; return [(p.x - f.x) / f.w, (p.y - f.y) / f.h]; };
  const clamp01 = n => [Math.min(1, Math.max(0, n[0])), Math.min(1, Math.max(0, n[1]))];
  function cropDown(e) {
    const at = document.elementFromPoint(e.clientX, e.clientY), near = q => (e.target.closest && e.target.closest(q)) || (at && at.closest(q));
    const rb = near("#crop .cratio button");
    if (rb && rb.dataset.cropend) { e.preventDefault(); return rb.dataset.cropend === "done" ? applyCrop() : endCrop(); }   // ↵ and Esc by the mouse
    if (rb) { cropKeep(); cropRatio(rb.dataset.ratio); return; }
    if (near("#crop .cratio")) return;
    if (near("#crop .vtin")) return trimDown(e);
    stage.setPointerCapture(e.pointerId);
    // the crop box may be redrawn by the time this runs (focus, render): its handle is then a detached node, so find it by its box
    const under = [...document.querySelectorAll("#crop .h")].find(h => {
      const r = h.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    });
    const t = e.target, hc = (t.classList && t.classList.contains("h") && t.dataset.c) || (under && under.dataset.c);
    const p = toWorld(e.clientX, e.clientY), raw = normOf(p), n = clamp01(raw), s = cropState, c = s.c;
    const inWin = raw[0] >= c[0] && raw[0] <= c[2] && raw[1] >= c[1] && raw[1] <= c[3];
    cropKeep();   // ⌘Z
    if (hc) s.act = { kind: "corner", c: hc, c0: [...c] };
    // inside the frame a drag moves it, cropped or not (B-04); ⇧ or a press on the dim part outside it draws a new one
    else if (inWin && !e.shiftKey) s.act = { kind: "move", n, c0: [...c] };
    else if (inside(p, s.full)) s.act = { kind: "new", n };
    else { s.undo.pop(); s.redo = s.redoWas; }   // a press beside the picture changes nothing (P4 B-46: it applied the crop); ↵ applies, Esc cancels
  }
  function cropMove(e) {
    const s = cropState; if (s.tact) return trimMove(e); if (!s.act) return;
    const n = clamp01(normOf(toWorld(e.clientX, e.clientY))), a = s.act, alt = e.altKey;
    // ⌥ works from the centre here too, as when resizing anything (owner 2026-10-02: "why does alt not work in crop"); it can be pressed
    // or let go in the middle of a drag
    if (s.ratio && a.kind === "new") s.c = ratioRect(a.n[0], a.n[1], n[0] >= a.n[0] ? 1 : -1, n[1] >= a.n[1] ? 1 : -1, n, alt, 0);
    else if (s.ratio && a.kind === "corner" && a.c.length === 1) s.c = ratioEdge(a.c0, a.c, n, alt);
    else if (s.ratio && a.kind === "corner") {
      const c0 = a.c0, sx = a.c.includes("w") ? -1 : 1, sy = a.c.includes("n") ? -1 : 1;
      s.c = ratioRect(alt ? (c0[0] + c0[2]) / 2 : (sx > 0 ? c0[0] : c0[2]), alt ? (c0[1] + c0[3]) / 2 : (sy > 0 ? c0[1] : c0[3]), sx, sy, n, alt, alt ? MIN / 2 : MIN);
    }
    else if (a.kind === "new" && alt) {
      const hw = Math.min(Math.abs(n[0] - a.n[0]), a.n[0], 1 - a.n[0]), hh = Math.min(Math.abs(n[1] - a.n[1]), a.n[1], 1 - a.n[1]);
      s.c = [a.n[0] - hw, a.n[1] - hh, a.n[0] + hw, a.n[1] + hh];
    } else if (a.kind === "new") s.c = [Math.min(a.n[0], n[0]), Math.min(a.n[1], n[1]), Math.max(a.n[0], n[0]), Math.max(a.n[1], n[1])];
    else if (a.kind === "corner" && alt) {
      const c0 = a.c0, cx = (c0[0] + c0[2]) / 2, cy = (c0[1] + c0[3]) / 2, c = s.c;
      if (/[we]/.test(a.c)) { const hw = Math.max(MIN / 2, Math.min(Math.abs(n[0] - cx), cx, 1 - cx)); c[0] = cx - hw; c[2] = cx + hw; } else { c[0] = c0[0]; c[2] = c0[2]; }
      if (/[ns]/.test(a.c)) { const hh = Math.max(MIN / 2, Math.min(Math.abs(n[1] - cy), cy, 1 - cy)); c[1] = cy - hh; c[3] = cy + hh; } else { c[1] = c0[1]; c[3] = c0[3]; }
    }
    else if (a.kind === "move") {
      const w = a.c0[2] - a.c0[0], h = a.c0[3] - a.c0[1];
      const x = Math.min(1 - w, Math.max(0, a.c0[0] + n[0] - a.n[0])), y = Math.min(1 - h, Math.max(0, a.c0[1] + n[1] - a.n[1]));
      s.c = [x, y, x + w, y + h];
    } else {   // a corner or an edge, free
      const c = s.c;
      if (a.c.includes("w")) c[0] = Math.min(n[0], c[2] - MIN); if (a.c.includes("e")) c[2] = Math.max(n[0], c[0] + MIN);
      if (a.c.includes("n")) c[1] = Math.min(n[1], c[3] - MIN); if (a.c.includes("s")) c[3] = Math.max(n[1], c[1] + MIN);
    }
    drawCrop();
  }
  function cropUp() {
    const s = cropState; if (!s) return; if (s.tact) return trimUp();
    if (s.act && s.act.kind === "new" && (s.c[2] - s.c[0] < MIN || s.c[3] - s.c[1] < MIN)) s.c = [...cropOf(board.items[s.id])];
    const u = s.undo[s.undo.length - 1]; if (u && u.c.join() === s.c.join()) { s.undo.pop(); s.redo = s.redoWas || s.redo; }   // nothing changed: no step
    s.act = null; drawCrop();
  }

  Object.assign(window, { CROP_RATIOS, RATIO_NAMES, ratioInner, ratioAttrs, startCrop, drawCrop, cropRatio, cropReset, cropKeep, cropStep, cropDown, cropMove, cropUp });
})();
