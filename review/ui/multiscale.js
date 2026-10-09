// Scaling several selected things together (owner 2026-10-07: «я три штуки выбрал, не могу их скалировать одновременно, только по
// отдельности, а надо вместе»). As in Figma: one box around the selection, the corner squares and side strips of a single object, and a
// handle scales the whole selection about the opposite corner or side; ⌥ about the centre, ⇧ keeps the box's proportions.
// Positions follow the box on both axes. A thing that keeps its proportions when resized alone (a picture, a note, a heading, a timeline,
// a plugin's card) scales by one factor: the dragged side's, at a corner the factor of the box's longer side. Each keeps its place in the
// box: what is flush with an edge stays flush, the free room around it is what stretches. A selected group is one such thing: its frame
// and members by the same factor. A note's zone stretches with the box. canvas.html makes the gesture one undo step (commit on pointerup).
(() => {
  const MIN_S = 0.05;   // the box never folds below 5 % of its size and never turns inside out
  let api = null;   // canvas.html: board(), rectOf, bbox, kind(it): "note" | "text" | "tl" | "card" | "pic", reachRect, tlSize, handlesOn, z()
  // what a gesture changes: the selected things and the members of the selected groups, each once
  function targets(sel) {
    const b = api.board(), items = new Map(), groups = [];   // items: id -> the selected group it is in, or null
    for (const id of sel) {
      if (b.groups[id]) { groups.push(id); b.groups[id].members.forEach(m => { if (b.items[m]) items.set(m, id); }); }
      else if (b.items[id] && !items.has(id)) items.set(id, null);
    }
    return { items: [...items.keys()], groups, of: items };
  }
  function begin(sel, rc) {
    const b = api.board(), t = targets(sel), box = { ...api.bbox([...t.items, ...t.groups]) };
    const it0 = new Map(t.items.map(id => { const it = b.items[id]; return [id, { it: JSON.parse(JSON.stringify(it)), r: { ...api.rectOf(id) }, z: api.reachRect(it), g: t.of.get(id) }]; }));
    return { rc, box, it0, g0: new Map(t.groups.map(id => [id, { ...b.groups[id] }])), wide: box.w >= box.h };
  }
  // a thing's start along one axis: its share of the free room of the old box, put in the free room of the new one; a thing as long as
  // the box (one row) keeps the fixed side: a 0 the start, 1 the end, .5 the centre (⌥, or the other axis' strip)
  const place = (p, s, s1, o, l, o1, l1, a) => l - s > 1e-6 ? o1 + (p - o) / (l - s) * (l1 - s1) : o1 + (l1 - s1) * a;
  function apply(st, dx, dy, alt, shift) {
    const b = api.board(), B = st.box, c = st.rc, L = c.includes("w"), R = c.includes("e"), N = c.includes("n"), S = c.includes("s");
    const m = alt ? 2 : 1;   // with ⌥ the far side moves the other way, as on a single object
    let sx = Math.max(MIN_S, L ? (B.w - dx * m) / B.w : R ? (B.w + dx * m) / B.w : 1);
    let sy = Math.max(MIN_S, N ? (B.h - dy * m) / B.h : S ? (B.h + dy * m) / B.h : 1);
    const k = (L || R) && (N || S) ? (st.wide ? sx : sy) : L || R ? sx : sy;   // the factor of what keeps its proportions
    if (shift) sx = sy = k;
    const W = B.w * sx, H = B.h * sy;
    const ax = alt || !(L || R) ? .5 : L ? 1 : 0, ay = alt || !(N || S) ? .5 : N ? 1 : 0;   // where the box stays put on each axis
    const X = B.x + (B.w - W) * ax, Y = B.y + (B.h - H) * ay;
    // a selected group is one thing: its frame by the same factor, its members with it, so the group stays as it was, only bigger
    const G1 = new Map();
    for (const [id, g] of st.g0) {
      const o = b.groups[id]; if (!o) continue;
      o.w = g.w * k; o.h = g.h * k; o.x = place(g.x, g.w, o.w, B.x, B.w, X, W, ax); o.y = place(g.y, g.h, o.h, B.y, B.h, Y, H, ay); G1.set(id, o);
    }
    for (const [id, o] of st.it0) {
      const it = b.items[id]; if (!it) continue;
      const r = o.r, w1 = r.w * k, h1 = r.h * k, kind = api.kind(it), g0 = o.g && st.g0.get(o.g), g1 = o.g && G1.get(o.g);
      if (g1) { it.x = g1.x + (r.x - g0.x) * k; it.y = g1.y + (r.y - g0.y) * k; }
      else { it.x = place(r.x, r.w, w1, B.x, B.w, X, W, ax); it.y = place(r.y, r.h, h1, B.y, B.h, Y, H, ay); }
      if (kind === "text") { it.fs = o.it.fs * k; it.w = w1; it.h = h1; if (o.it.tw) it.tw = o.it.tw * k; }   // the redraw measures it again; a document's width too
      else if (kind === "tl") { it.fs = o.it.fs * k; it.len = o.it.len * k; it.points.forEach((q, i) => { q.t = o.it.points[i].t * k; }); api.tlSize(it); }
      else if (kind === "note") { it.w = o.it.w * k; it.h = o.it.h * k; }   // its type is a share of its width (NSIZE)
      else if (kind === "card") { it.w = o.it.w * k; it.h = o.it.h * k; }
      else it.w = o.it.w * k;   // a picture: its height comes from its proportions
      if (o.z && it.reach) {   // the zone stretches with the box (in a group, with the group), the note keeps its place in it
        const z = o.z, [zx, zy, zw, zh] = g1 ? [g1.x + (z.x - g0.x) * k, g1.y + (z.y - g0.y) * k, z.w * k, z.h * k] : [X + (z.x - B.x) * sx, Y + (z.y - B.y) * sy, z.w * sx, z.h * sy];
        it.reach = { l: Math.max(0, it.x - zx), t: Math.max(0, it.y - zy), r: Math.max(0, zx + zw - it.x - it.w), b: Math.max(0, zy + zh - it.y - Math.max(h1, it.w)) };
      }
    }
  }
  // the box, its side strips and corner squares in #handles (the classes of a single object's, data-mresize instead of data-resize)
  function draw(host, sel, drag) {
    const t = targets(sel), r = api.bbox([...t.items, ...t.groups]); if (!isFinite(r.w) || !isFinite(r.h)) return;
    const f = document.createElement("div"); f.className = "mbox";
    Object.assign(f.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px" }); host.appendChild(f);
    if (!api.handlesOn(r.w * api.z(), r.h * api.z())) return;
    const add = (cls, rc, x, y, st) => {
      const e = document.createElement("div"); e.className = cls; e.dataset.mresize = rc;
      if (drag && drag.mode === "mresize" && drag.st.rc === rc && cls === "h") e.classList.add("on");
      Object.assign(e.style, { left: x + "px", top: y + "px" }, st); host.appendChild(e);
    };
    const strip = "calc(14px / var(--z))";
    add("he", "n", r.x, r.y, { width: r.w + "px", height: strip, transform: "translate(0, -50%)", cursor: "ns-resize" });
    add("he", "s", r.x, r.y + r.h, { width: r.w + "px", height: strip, transform: "translate(0, -50%)", cursor: "ns-resize" });
    add("he", "w", r.x, r.y, { width: strip, height: r.h + "px", transform: "translate(-50%, 0)", cursor: "ew-resize" });
    add("he", "e", r.x + r.w, r.y, { width: strip, height: r.h + "px", transform: "translate(-50%, 0)", cursor: "ew-resize" });
    add("h", "nw", r.x, r.y, { cursor: "nwse-resize" }); add("h", "ne", r.x + r.w, r.y, { cursor: "nesw-resize" });
    add("h", "sw", r.x, r.y + r.h, { cursor: "nesw-resize" }); add("h", "se", r.x + r.w, r.y + r.h, { cursor: "nwse-resize" });
  }
  window.hyMultiScale = { init(a) { api = a; }, targets, begin, apply, draw, MIN_S };
})();
