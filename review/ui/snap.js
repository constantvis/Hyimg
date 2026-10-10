// Snapping guides on the board (owner decision 2026-10-10, П4 B-62, option (a), as in Figma): a card moved or resized snaps to the edges
// and centres of the other cards and group frames on screen when it comes within 6 px of one, and a thin line in the selection's colour
// shows each edge or centre that lines up. ⌘ held lets it go free. No rotation. Fast on a big board: the lines are gathered once a drag,
// only from what is on screen, at most CAP things, the nearest first; each move is a look through those few hundred numbers.
//   hySnap.near(lines, cands, t)      the pure part: lines of the thing moved, the candidates' lines, a reach; {d, c} the shift to the
//                                     nearest candidate within t (d 0, c null: none)
//   hySnap.move(drag, dx, dy, e)      canvas.html onMove, a drag of cards: the move snapped, [dx, dy], guides drawn
//   hySnap.resize(drag, dx, dy, e, m) canvas.html onMove, a card's or a group's corner or edge: the dragged edges snapped (m 2 with ⌥)
//   hySnap.clear()                    the drag ended: the guides go
// canvas.html's globals: board, cam, stage, rectOf, INSET.
(() => {
  if (window.hySnap) return;
  const PX = 6, CAP = 400, EPS = .01;
  function near(lines, cands, t) {
    let best = null;
    for (const l of lines) for (const c of cands) { const d = c - l; if (Math.abs(d) <= t && (!best || Math.abs(d) < Math.abs(best.d))) best = { d, c }; }
    return best || { d: 0, c: null };
  }
  const xs = r => [r.x, r.x + r.w / 2, r.x + r.w], ys = r => [r.y, r.y + r.h / 2, r.y + r.h];
  // what lies on screen, not moving: the cards and the group frames, the nearest CAP to the box b
  function gather(skip, b) {
    const sr = stage.getBoundingClientRect(), v = { x: cam.x, y: cam.y, w: sr.width / cam.z, h: sr.height / cam.z }, out = [];
    const on = r => r && r.w > 0 && r.x < v.x + v.w && r.x + r.w > v.x && r.y < v.y + v.h && r.y + r.h > v.y;
    for (const id in board.items) { if (skip.has(id)) continue; const r = rectOf(id); if (on(r)) out.push(r); }
    for (const id in board.groups) { if (skip.has(id)) continue; const r = board.groups[id]; if (on(r)) out.push(r); }
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2, dist = r => Math.hypot(r.x + r.w / 2 - cx, r.y + r.h / 2 - cy);
    const rs = out.length > CAP ? out.sort((p, q) => dist(p) - dist(q)).slice(0, CAP) : out;
    return { rs, X: rs.flatMap(xs), Y: rs.flatMap(ys) };
  }
  let layer = null;
  function draw(lx, ly, box, rs) {   // a line at each x in lx and each y in ly, from the moved box to the farthest thing on it
    if (!layer || !layer.isConnected) { layer = document.createElement("div"); layer.id = "snapg"; layer.setAttribute("aria-hidden", "true"); document.getElementById("world").appendChild(layer); }
    let h = "";
    for (const x of lx) {
      const on = rs.filter(r => xs(r).some(v => Math.abs(v - x) < EPS)), y0 = Math.min(box.y, ...on.map(r => r.y)), y1 = Math.max(box.y + box.h, ...on.map(r => r.y + r.h));
      h += `<i class="v" style="left:${x}px;top:${y0}px;height:${y1 - y0}px"></i>`;
    }
    for (const y of ly) {
      const on = rs.filter(r => ys(r).some(v => Math.abs(v - y) < EPS)), x0 = Math.min(box.x, ...on.map(r => r.x)), x1 = Math.max(box.x + box.w, ...on.map(r => r.x + r.w));
      h += `<i class="h" style="top:${y}px;left:${x0}px;width:${x1 - x0}px"></i>`;
    }
    if (layer._h !== h) { layer.innerHTML = h; layer._h = h; }
  }
  function clear() { if (layer && layer._h) { layer.innerHTML = ""; layer._h = ""; } }
  // the lines of box that sit on a candidate line now
  const hits = (mine, all) => mine.filter(l => all.some(c => Math.abs(c - l) < EPS));
  function move(d, dx, dy, e) {
    if (e && e.metaKey) { clear(); return [dx, dy]; }
    if (!d.snap) {
      const rs = d.start.map(([, r]) => r), x0 = Math.min(...rs.map(r => r.x)), y0 = Math.min(...rs.map(r => r.y));
      const b0 = { x: x0, y: y0, w: Math.max(...rs.map(r => r.x + r.w)) - x0, h: Math.max(...rs.map(r => r.y + r.h)) - y0 };
      d.snap = { b0, ...gather(new Set(d.start.map(([id]) => id)), b0) };
    }
    const S = d.snap, t = PX / cam.z, b = { ...S.b0, x: S.b0.x + dx, y: S.b0.y + dy };
    const sx = d.axis === "y" ? { d: 0 } : near(xs(b), S.X, t), sy = d.axis === "x" ? { d: 0 } : near(ys(b), S.Y, t);
    dx += sx.d; dy += sy.d; b.x += sx.d; b.y += sy.d;
    draw(hits(xs(b), S.X), hits(ys(b), S.Y), b, S.rs);
    return [dx, dy];
  }
  function resize(d, dx, dy, e, m = 1) {
    if (e && e.metaKey) { clear(); return [dx, dy]; }
    const r0 = d.r0, c = d.rc || "se", L = c.includes("w"), R = c.includes("e"), T = c.includes("n"), B = c.includes("s");
    if (!d.snap) d.snap = gather(new Set([d.id]), r0);
    const S = d.snap, t = PX / cam.z, keep = !!(board.items[d.id] && !board.items[d.id].type);   // a picture keeps its proportions: x only
    const ex = L ? r0.x + m * dx : R ? r0.x + r0.w + m * dx : null, ey = keep ? null : T ? r0.y + m * dy : B ? r0.y + r0.h + m * dy : null;
    const sx = ex == null ? { d: 0 } : near([ex], S.X, t), sy = ey == null ? { d: 0 } : near([ey], S.Y, t);
    dx += sx.d / m; dy += sy.d / m;
    const box = { x: Math.min(r0.x, ex ?? r0.x), y: Math.min(r0.y, ey ?? r0.y), w: Math.abs((ex ?? r0.x + r0.w) - r0.x) || r0.w, h: r0.h };
    draw(sx.c != null ? [sx.c] : [], sy.c != null ? [sy.c] : [], box, S.rs);
    return [dx, dy];
  }
  const css = document.createElement("style");
  css.textContent = `#snapg { position: absolute; left: 0; top: 0; width: 0; height: 0; overflow: visible; pointer-events: none; z-index: 6; }
#snapg i { position: absolute; display: block; background: var(--sel); }
#snapg i.v { width: calc(1px / var(--z, 1)); margin-left: calc(-.5px / var(--z, 1)); }
#snapg i.h { height: calc(1px / var(--z, 1)); margin-top: calc(-.5px / var(--z, 1)); }`;
  (document.head || document.documentElement).appendChild(css);
  window.hySnap = { near, move, resize, clear, PX };
})();
