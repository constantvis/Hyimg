// Move to page, the board's side of it (canvas.html moveToPage, owner 2026-10-06): what goes with the selection, where it lands on the
// other page, putting it there and taking it off again. Moved here from canvas.html with the connectors (P4 B-10, П4 audit 2026-10-10:
// arrows between moved cards were left behind): a connector (board.links) with both ends among the things that go goes along, under an
// id free on the other page; one with a single end there is dropped and counted in the note; the note's «Undo» brings them all back.
function moveSet(ids) { return hySel.carry(ids, true); }   // what a drag carries, the board's one rule (ui/boardsel.js, P4 B-24)
// the annotations of the moved things go with them, and back with ⌘Z or the note's Undo (ui/comments.js carry, P4 B-32)
function moveThreads(rec, back) {
  if (!window.hyComments || !rec.map) return null;
  const m = back ? Object.fromEntries(Object.entries(rec.map).map(([a, b]) => [b, a])) : rec.map;
  return hyComments.carry(back ? rec.dest : rec.src, back ? rec.src : rec.dest, m);
}
function roomOf(b, ids, gids) {   // the boxes things take on board b: items (a note at least a square, and its zone) and group frames
  const out = [];
  ids.forEach(id => {
    const it = b.items[id]; if (!it || it.x == null || it.y == null) return;
    out.push({ x: it.x, y: it.y, w: it.w, h: isNote(it) ? Math.max(itemH(it), it.w) : itemH(it) });
    const z = isNote(it) && reachRect(it); if (z) out.push(z);
  });
  gids.forEach(g => { const r = b.groups[g]; if (r) out.push({ x: r.x, y: r.y, w: r.w, h: r.h }); });
  return out.filter(r => [r.x, r.y, r.w, r.h].every(Number.isFinite));
}
function boxOf(rs) {
  const x = Math.min(...rs.map(r => r.x)), y = Math.min(...rs.map(r => r.y)); return { x, y, w: Math.max(...rs.map(r => r.x + r.w)) - x, h: Math.max(...rs.map(r => r.y + r.h)) - y };
}
// where a box lands on board b: where it is when nothing there is within half a group's air of it, else right of everything, at the top
function landing(b, box, air) {
  const obs = roomOf(b, Object.keys(b.items), Object.keys(b.groups)), pad = { x: box.x - air / 2, y: box.y - air / 2, w: box.w + air, h: box.h + air };
  if (!obs.some(o => hitR(pad, o))) return { dx: 0, dy: 0 };
  const all = boxOf(obs); return { dx: Math.round(all.x + all.w + air - box.x), dy: Math.round(all.y - box.y) };
}
// rec.load: the things as they land on the other page, under the ids they have there; put there again (a redo) where those ids are free
function putOn(b, rec) {
  Object.entries(rec.load.items).forEach(([id, it]) => { if (!b.items[id]) b.items[id] = JSON.parse(JSON.stringify(it)); });
  Object.entries(rec.load.groups).forEach(([id, g]) => { if (!b.groups[id]) b.groups[id] = JSON.parse(JSON.stringify(g)); });
  Object.entries(rec.load.links || {}).forEach(([id, c]) => { if (!(b.links || {})[id]) (b.links || (b.links = {}))[id] = { ...c }; });
  Object.values(rec.load.items).flatMap(picsOf).forEach(p => delete b.removed[p]);
}
function takeOff(b, rec) {   // the moved things off a board again, and every arrow and membership pointing at them
  const gone = new Set([...Object.keys(rec.load.items), ...Object.keys(rec.load.groups)]);
  gone.forEach(id => { delete b.items[id]; delete b.groups[id]; });
  Object.values(b.groups).forEach(g => g.members = g.members.filter(m => !gone.has(m)));
  Object.values(b.items).forEach(n => { if (isNote(n) && n.to) n.to = n.to.filter(t => !gone.has(t)); });
  if (window.hyConn) hyConn.prune(b);   // and the connectors with an end among them
}

// the connectors of a move from board b, I: the ids that go. along: both ends go; touching: any end goes (the note's «Undo»); cut: dropped
function moveLinks(b, I) {
  const along = {}, touching = {}; let cut = 0;
  Object.entries(b.links || {}).forEach(([id, c]) => {
    const f = I.has(c.from), t = I.has(c.to); if (!f && !t) return;
    touching[id] = JSON.parse(JSON.stringify(c)); if (f && t) along[id] = touching[id]; else cut++;
  });
  return { along, touching, cut };
}
function landLinks(b, along, map) {   // the connectors going along as they land on board b: the things' ids there, a free id of their own
  const out = {};
  Object.entries(along).forEach(([id, c]) => { out[(b.links || {})[id] ? "c" + Math.random().toString(36).slice(2, 9) : id] = { ...c, from: map[c.from] || c.from, to: map[c.to] || c.to }; });
  return out;
}
function linksBack(b, links) {   // the note's «Undo» on the page they left: each connector that touched them, where both its ends are again
  const here = i => !!(b.items[i] || b.groups[i]);
  Object.entries(links || {}).forEach(([id, c]) => { if (here(c.from) && here(c.to) && !(b.links || {})[id]) (b.links || (b.links = {}))[id] = { ...c }; });
}
