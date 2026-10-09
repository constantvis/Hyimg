// Arrange makes a grid (owner 2026-10-08: «добавить в нашу систему Arrange: пользователю нативно и удобно, он даже не поймет, что таблицей
// что-то разложил, а для агента структура — win-win»). ⌥A (a block), ⌥S (a row), ⌥D (tidy, when what it lays out is a grid) and «Make grid»
// in the right click's «Arrange ›» record the arrangement on the page, board.grids[id] = {members (rows top to bottom, each left to right),
// cols, rows, gap, cell: "fit", head: {row, col} when headings fill the first row or column}. review/grids.py is the same model for hy.py
// and the server's merge. No frame is drawn: a faint «Grid 4 × 3» while a member is selected or dragged.
//
// It behaves as a soft auto-layout: a member dragged within its grid takes the cell under the pointer and the others reflow (animated with
// the app's curve); dragged out it leaves and the gap closes; a picture or card dropped on a grid goes into the cell under the pointer (an
// ⌥-drag copy too); ⌘D puts the copy right after its original; a member deleted or resized reflows the grid from its old top left. Cells are
// "fit": a column is as wide as its widest member, a row as tall as its tallest, a member at its cell's top left. Every gesture is one undo
// step (the grids ride in the board's snapshot). canvas.html calls: arranged (the three Arrange commands), settle (each commit), moving and
// drop (a drag), dup (⌘D), draw (the handles), entry and act (the right click, built by ui/arrange.js), merged (ui/merge.js).
(() => {
  const GAP = 24, EASE = "cubic-bezier(.32,.72,0,1)";
  const items = b => b.items || {}, table = b => b.grids || {};
  // a thing's box on the board, as canvas.html rectOf/itemH for the kinds a grid holds
  function rect(b, id) {
    const it = items(b)[id]; if (!it) return null;
    if (it.type) return { x: it.x, y: it.y, w: it.w, h: it.h || it.fs * 1.2 };
    const c = it.crop || [0, 0, 1, 1];
    return { x: it.x, y: it.y, w: it.w, h: it.w * ((c[3] - c[1]) / (it.ar || 1)) / (c[2] - c[0]) };
  }
  // what a grid holds: a picture, a video, a PDF, a plugin's card, a heading; never a note or a timeline
  const gridable = it => !!it && it.type !== "note" && it.type !== "timeline" && !!(it.type || it.path) && it.x != null;
  const placed = (b, ids) => ids.filter(id => gridable(items(b)[id]));
  const of = (b, id) => Object.keys(table(b)).find(g => table(b)[g].members.includes(id)) || null;

  // reading order: rows top to bottom (a thing joins a row when its top is within half the shortest height of the row's first), left to right
  function rowsOf(b, ids) {
    const R = new Map(ids.map(id => [id, rect(b, id)])); if (!R.size) return [];
    const tol = Math.min(...[...R.values()].map(r => r.h)) / 2, out = [];
    [...R.keys()].sort((p, q) => R.get(p).y - R.get(q).y || R.get(p).x - R.get(q).x).forEach(id => {
      const row = out[out.length - 1]; if (row && Math.abs(R.get(id).y - R.get(row[0]).y) <= tol) row.push(id); else out.push([id]);
    });
    return out.map(r => r.sort((p, q) => R.get(p).x - R.get(q).x));
  }
  function origin(b, ids) {
    const rs = ids.map(id => rect(b, id)).filter(Boolean);
    return rs.length ? { x: Math.min(...rs.map(r => r.x)), y: Math.min(...rs.map(r => r.y)) } : { x: 0, y: 0 };
  }
  // the cells of a grid: {pos: Map id -> {x, y}, cells [{x, y, w, h}] in member order, shape}; R(id) may stand in for a member's box
  function layout(b, g, at, R = id => rect(b, id)) {
    const ms = g.members.filter(m => items(b)[m]), n = ms.length, gap = g.gap ?? GAP;
    const cols = Math.max(1, Math.min(g.cols || 1, n || 1)), rows = n ? Math.ceil(n / cols) : 0, rs = ms.map(R);
    const colw = [...Array(cols)].map((_, c) => Math.max(0, ...rs.filter((_, k) => k % cols === c).map(r => r.w)));
    const rowh = [...Array(rows)].map((_, r) => Math.max(0, ...rs.slice(r * cols, r * cols + cols).map(r => r.h)));
    const o = at || origin(b, ms), sum = (a, k) => a.slice(0, k).reduce((s, v) => s + v + gap, 0);
    const pos = new Map(), cells = [];
    ms.forEach((m, k) => { const c = k % cols, r = Math.floor(k / cols), x = o.x + sum(colw, c), y = o.y + sum(rowh, r); pos.set(m, { x, y }); cells.push({ x, y, w: colw[c], h: rowh[r] }); });
    const w = colw.reduce((s, v) => s + v, 0) + gap * (cols - 1), h = rowh.reduce((s, v) => s + v, 0) + gap * Math.max(0, rows - 1);
    return { pos, cells, shape: { cols, rows, colw, rowh, x: o.x, y: o.y, w, h } };
  }
  function heads(b, g) {
    const ms = g.members.filter(m => items(b)[m]), cols = Math.max(1, Math.min(g.cols || 1, ms.length || 1)), text = m => items(b)[m].type === "text";
    const h = {}; if (ms.length > cols && ms.slice(0, cols).every(text)) h.row = true;
    if (cols > 1 && ms.length > cols && ms.filter((_, k) => k % cols === 0).every(text)) h.col = true;
    return h;
  }
  function reflow(b, gid, at) {
    const g = table(b)[gid]; g.members = [...new Set(g.members)].filter(m => items(b)[m]);
    const L = layout(b, g, at); L.pos.forEach((p, m) => { items(b)[m].x = p.x; items(b)[m].y = p.y; });
    g.rows = L.shape.rows; const h = heads(b, g); if (Object.keys(h).length) g.head = h; else delete g.head;
    return L.shape;
  }
  function dropSmall(b) { for (const [gid, g] of Object.entries(table(b))) if (g.members.filter(m => items(b)[m]).length < 2) delete b.grids[gid]; }
  // ids out of the grids they are in; those close the gap from where they stood
  function leave(b, ids, keep) {
    const out = new Set(ids);
    for (const [gid, g] of Object.entries(table(b))) {
      if (gid === keep || !g.members.some(m => out.has(m))) continue;
      const at = origin(b, g.members); g.members = g.members.filter(m => !out.has(m));
      if (g.members.filter(m => items(b)[m]).length >= 2) reflow(b, gid, at);
    }
    dropSmall(b);
  }
  // a grid of these things (in reading order unless ordered), from their top left; the same set as a grid that exists keeps its id
  function make(b, ids, cols, ordered, newId) {
    ids = [...new Set(placed(b, ids))]; if (ids.length < 2) return null;
    const at = origin(b, ids), rows = rowsOf(b, ids); if (!ordered) ids = rows.flat();
    const gid = Object.keys(table(b)).find(k => { const m = table(b)[k].members; return m.length === ids.length && ids.every(i => m.includes(i)); }) || newId("gr");
    leave(b, ids, gid);
    (b.grids || (b.grids = {}))[gid] = { members: ids, cols: Math.max(1, cols || Math.max(...rows.map(r => r.length))), rows: 0, gap: GAP, cell: "fit" };
    reflow(b, gid, at); return gid;
  }
  // a merged board (ui/merge.js): a grid whose members came from both sides is laid out again; members gone leave it
  function merged(out, local, remote) {
    for (const [gid, g] of Object.entries(table(out))) {
      const a = (table(local)[gid] || {}).members, c = (table(remote)[gid] || {}).members, same = x => !!x && x.join("\n") === g.members.join("\n");
      if (!same(a) && !same(c) && g.members.filter(m => items(out)[m]).length >= 2) reflow(out, gid);
    }
    prune(out, null);
    if (out.grids && !Object.keys(out.grids).length) delete out.grids;
  }
  // members gone, or a member's size changed: the grid reflows from where it stood before (from where it is now when all of it changed)
  function prune(b, B) {
    for (const [gid, g] of Object.entries(table(b))) {
      const was = B && table(B)[gid], live = g.members.filter(m => items(b)[m]);
      const sized = B ? live.filter(m => { const p = rect(B, m), q = rect(b, m); return !p || Math.abs(p.w - q.w) > .01 || Math.abs(p.h - q.h) > .01; }) : [];
      const changed = live.length !== g.members.length || sized.length || (was && was.members.join("\n") !== g.members.join("\n"));
      g.members = live; if (!changed || live.length < 2 || (B && !was)) continue;   // a grid this edit made is laid out by what made it
      const all = sized.length === live.length && was && was.members.length === live.length;
      reflow(b, gid, B && !all ? origin(B, (was || g).members.filter(m => items(B)[m])) : null);
    }
    dropSmall(b);
  }
  // the cell under a point: the nearest cell centre, of the grid's cells plus one more after its last (where a new thing would go)
  function slot(cells, p, extra) {
    const all = extra ? [...cells, extra] : cells; let best = 0, bd = Infinity;
    all.forEach((c, k) => { const d = Math.hypot(c.x + c.w / 2 - p.x, c.y + c.h / 2 - p.y); if (d < bd) { bd = d; best = k; } });
    return best;
  }
  const nextCell = (L, g, r) => {   // the cell after the last one, sized like the thing that goes there
    const n = L.cells.length, cols = Math.max(1, g.cols || 1), c = n % cols, gap = g.gap ?? GAP, s = L.shape;
    const x = s.x + s.colw.slice(0, c).reduce((a, v) => a + v + gap, 0), y = c ? s.y + s.h - s.rowh[s.rows - 1] : s.y + s.h + gap;
    return { x, y, w: r.w, h: r.h };
  };

  /* ---------------- the board (canvas.html's globals: board, sel, render, toWorld, EL, HY) ---------------- */
  const live = () => typeof board !== "undefined" && board && board.grids && Object.keys(board.grids).length;
  const ids0 = ids => ids.filter(id => board.items[id]);
  // the three Arrange commands: what they laid out becomes a grid; cols null (⌥D) only when what it laid out is a grid already
  function arranged(ids, cols, ordered) {
    ids = ids0(ids); const ok = placed(board, ids); if (ok.length < 2) return;
    if (cols == null) {
      const rows = rowsOf(board, ok), c = Math.max(...rows.map(r => r.length));
      const regular = ok.length === ids.length && rows.slice(0, -1).every(r => r.length === c);
      const g = { members: rows.flat(), cols: c, gap: GAP }, L = regular && layout(board, g);
      const fits = L && [...L.pos].every(([m, p]) => Math.abs(board.items[m].x - p.x) < 1 && Math.abs(board.items[m].y - p.y) < 1);
      if (!fits) { leave(board, ids); return; }
      make(board, rows.flat(), c, true, HY.uid); return;
    }
    make(board, ok, cols, ordered, HY.uid);
  }
  // each commit: what the edit did to a grid's members (deleted, resized, a copy added) reflows it
  function settle(before) { if (!live()) return; let B = null; try { B = JSON.parse(before); } catch {} prune(board, B); if (!Object.keys(board.grids).length) delete board.grids; }
  function dup(src, copy) { const g = of(board, src); if (!g) return; const m = board.grids[g].members; m.splice(m.indexOf(src) + 1, 0, copy); }

  // a drag: d.start [[id, its box at the start]], d.last the pointer; the plan is kept on the drag (d.grid)
  function plan(d) {
    if (d.start.some(([id]) => board.groups[id])) return null;
    const D = d.start.map(([id]) => id).filter(id => board.items[id]); if (!D.length || D.some(id => !gridable(board.items[id]))) return null;
    if (!d.grid) {   // the grids as they stood when the drag began: a dragged member at its start box
      const st = new Map(d.start), R = id => st.get(id) || rect(board, id), gs = {};
      for (const [gid, g] of Object.entries(table(board))) {
        const mine = g.members.filter(m => D.includes(m)); if (mine.length && mine.length === g.members.length) continue;   // the whole grid moves
        const rs = g.members.filter(m => board.items[m]).map(R), at = { x: Math.min(...rs.map(r => r.x)), y: Math.min(...rs.map(r => r.y)) };
        gs[gid] = { members: [...g.members], mine, L: layout(board, g, at, R) };
      }
      d.grid = { gs, D, flow: new Set() };
    }
    return d.grid;
  }
  function moving(d) {
    if (!live() || !d.last) return; const P = plan(d); if (!P) return;
    const p = toWorld(d.last.clientX, d.last.clientY), pad = GAP * 2;
    const inA = s => p.x >= s.x - pad && p.x <= s.x + s.w + pad && p.y >= s.y - pad && p.y <= s.y + s.h + pad;
    const target = Object.keys(P.gs).filter(gid => inA(P.gs[gid].L.shape)).sort((a, c) => P.gs[a].L.shape.w * P.gs[a].L.shape.h - P.gs[c].L.shape.w * P.gs[c].L.shape.h)[0] || null;
    P.target = target; P.order = null; P.slot = null;
    for (const [gid, G] of Object.entries(P.gs)) {   // the target makes room, a source closes its gap, any other stands as it began
      const g = board.grids[gid]; if (!g) continue;
      const rest = G.members.filter(m => !P.D.includes(m) && board.items[m]);
      let order = rest;
      if (gid === target) {
        const r0 = rect(board, P.D[0]), extra = G.mine.length ? null : nextCell(G.L, g, r0);
        const k = Math.min(slot(G.L.cells, p, extra), rest.length); order = [...rest.slice(0, k), ...P.D, ...rest.slice(k)];
        P.order = order;
      }
      const L = layout(board, { ...g, members: order }, G.L.shape);
      L.pos.forEach((q, m) => {
        if (P.D.includes(m)) { if (gid === target) P.slot = L.cells[order.indexOf(m)]; return; }
        const it = board.items[m]; if (it.x === q.x && it.y === q.y) return;
        flow(m); it.x = q.x; it.y = q.y;
      });
    }
  }
  function flow(id) {   // a card glides to its new cell
    const el = EL.get(id); if (!el) return;
    el.style.transition = `left .26s ${EASE}, top .26s ${EASE}`; clearTimeout(el._gf); el._gf = setTimeout(() => { el.style.transition = ""; }, 320);
  }
  // the pointer came up: the dragged things take their cells (or leave), one undo step with the drag (canvas.html commits after)
  function drop(d) {
    const P = d.grid; if (!P || !live()) return;
    for (const [gid, g] of Object.entries(board.grids)) {   // the dragged leave every grid but the target; a source closes its gap from its old top left
      if (gid === P.target || !g.members.some(m => P.D.includes(m))) continue;
      g.members = g.members.filter(m => !P.D.includes(m));
      if (P.gs[gid] && g.members.filter(m => board.items[m]).length >= 2) reflow(board, gid, P.gs[gid].L.shape);
    }
    if (P.target && board.grids[P.target]) { board.grids[P.target].members = P.order; P.D.forEach(flow); reflow(board, P.target, P.gs[P.target].L.shape); }
    dropSmall(board); if (!Object.keys(board.grids).length) delete board.grids;
  }
  // a faint «Grid C × R» round the grids of the selection, and the cell a drag would drop into
  function draw(h, s, d) {
    if (!live()) return;
    const P = d && d.grid, show = new Set(P && P.target ? [P.target] : []);
    if (!d || !d.moved) for (const id of s) { const g = of(board, id); if (g) show.add(g); if (show.size >= 4) break; }
    for (const gid of show) {
      const g = board.grids[gid], L = P && gid === P.target ? layout(board, { ...g, members: P.order }, P.gs[gid].L.shape) : layout(board, g), sh = L.shape;
      const el = document.createElement("div"); el.className = "gridhint" + (P && gid === P.target ? " on" : "");
      Object.assign(el.style, { left: sh.x + "px", top: sh.y + "px", width: sh.w + "px", height: sh.h + "px" });
      el.innerHTML = `<b>${T("Grid {c} × {r}", { c: sh.cols, r: sh.rows })}</b>`; h.appendChild(el);
    }
    if (!P || !P.slot) return;
    const c = P.slot, el = document.createElement("div"); el.className = "gridslot";
    Object.assign(el.style, { left: c.x + "px", top: c.y + "px", width: c.w + "px", height: c.h + "px" }); h.appendChild(el);
  }
  // the right click's «Arrange ›» lives in ui/arrange.js (tidy, grid and table, the layout patterns); canvas.html asks here
  const entry = ids => window.hyArrange ? hyArrange.entry(ids) : null, act = (b, ids) => !!window.hyArrange && hyArrange.act(b, ids);
  const css = document.createElement("style");
  css.textContent = `#handles .gridhint { position: absolute; box-sizing: border-box; pointer-events: none; border-radius: calc(6px / var(--z, 1));
  outline: calc(1px / var(--z, 1)) dashed color-mix(in srgb, var(--sel) 45%, transparent); outline-offset: calc(6px / var(--z, 1)); }
#handles .gridhint.on { outline-color: color-mix(in srgb, var(--sel) 80%, transparent); }
#handles .gridhint b { position: absolute; left: 0; bottom: 100%; transform: scale(calc(1 / var(--z, 1))); transform-origin: 0 100%; padding: 0 0 18px;
  font: 500 11px var(--sans); color: var(--sel); opacity: .8; white-space: nowrap; }
#handles .gridslot { position: absolute; pointer-events: none; border-radius: calc(6px / var(--z, 1)); background: color-mix(in srgb, var(--sel) 14%, transparent);
  transition: left .18s ${EASE}, top .18s ${EASE}; }`;
  (document.head || document.documentElement).appendChild(css);
  window.hyGrid = { rect, rowsOf, layout, reflow, make, leave, prune, merged, slot, heads, of, gridable, placed, arranged, settle, dup, moving, drop, draw, entry, act };
})();
