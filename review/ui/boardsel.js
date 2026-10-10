// What a selection means to the board's commands (П4 audit 2026-10-10). One definition of what a group carries and of the cards a command
// acts on, so a drag, ⌫, ⌘C, ⌘X, ⌘D, Move to page and the arrow keys take the same things (P4 B-23, B-24: a drag of a group left a group
// lying inside its frame behind, ⌘D and ⌥A on a selected group did nothing while Arrange worked on it).
//   hySel.carry(ids, zones)   { items, groups }: the things themselves, a group with its members and the groups lying wholly inside its
//                             frame (and theirs); zones: a note with the pictures whose centre is in its dashed zone (a drag, Move to page)
//   hySel.pick(ids)           the cards a command works on: a selected group gives its cards (Arrange's pick, ⌥A ⌥S ⌥D, F, 1…0, ⌘G)
//   hySel.tops()              ⌘A (P4 B-21): the groups no other group's frame holds, and the cards none of them carries
//   hySel.clone(ids, dx, dy)  ⌘D and ⌥-drag: copies of what ids carry, dx dy off; the groups with copies of their members, the arrows
//                             among them (P4 B-29); { map: old id -> new, out: the copies of ids themselves }
// canvas.html's globals: board, sel, rectOf, isNote, isPic, reachRect, inside, uid, dupOf, regroup; ui/connectors.js hyConn.copyAmong.
(() => {
  if (window.hySel) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const holds = (g, h) => h.x >= g.x && h.y >= g.y && h.x + h.w <= g.x + g.w && h.y + h.h <= g.y + g.h;
  function carry(ids, zones) {
    const items = new Set(), groups = new Set(), G = board.groups;
    const addGroup = gid => {
      const g = G[gid]; if (!g || groups.has(gid)) return; groups.add(gid);
      g.members.forEach(m => { if (board.items[m]) items.add(m); });
      for (const [o, h] of Object.entries(G)) if (o !== gid && holds(g, h)) addGroup(o);
    };
    [...ids].forEach(id => { if (board.items[id]) items.add(id); else addGroup(id); });
    if (zones) [...items].forEach(s => {
      const z = isNote(board.items[s]) && reachRect(board.items[s]); if (!z) return;
      for (const id in board.items) { if (items.has(id) || !isPic(board.items[id])) continue; const r = rectOf(id); if (inside({ x: r.x + r.w / 2, y: r.y + r.h / 2 }, z)) items.add(id); }
    });
    return { items: [...items], groups: [...groups] };
  }
  const pick = ids => carry(ids || [...sel]).items;
  function tops() {
    const G = board.groups, ks = Object.keys(G);
    const top = ks.filter(g => !ks.some(o => o !== g && holds(G[o], G[g]) && !(holds(G[g], G[o]) && o > g)));   // two equal frames: one of them
    const held = new Set(carry(top).items);
    return [...top, ...Object.keys(board.items).filter(id => !held.has(id))];
  }
  function clone(ids, dx = 0, dy = 0) {
    const c = carry(ids), map = {}, out = new Set();
    c.items.forEach(id => { const it = board.items[id], [n, k] = dupOf(it, { x: it.x + dx, y: it.y + dy }); board.items[n] = k; map[id] = n; });
    c.groups.forEach(g => { const o = board.groups[g], n = uid("g"); board.groups[n] = { ...JSON.parse(JSON.stringify(o)), x: o.x + dx, y: o.y + dy,
      members: o.members.filter(m => map[m]).map(m => map[m]) }; map[g] = n; });
    Object.values(map).forEach(n => { const it = board.items[n]; if (it && isNote(it) && it.to) it.to = it.to.map(t => map[t] || t); });   // a copied note points at the copies
    if (window.hyConn && hyConn.copyAmong) hyConn.copyAmong(board, map);
    [...ids].forEach(id => { if (map[id]) out.add(map[id]); });
    const inG = new Set(c.groups.flatMap(g => board.groups[map[g]].members));   // cards of a copied group stay in it
    regroup(Object.values(map).filter(n => board.items[n] && !inG.has(n)));
    return { map, out };
  }
  // what a delete took, in words: «2 pictures, 1 note, 1 group»; before: the board's string before it
  function words(b, items, groups) {
    const notes = items.filter(id => isNote(b.items[id])), rest = items.filter(id => b.items[id] && !isNote(b.items[id]));
    return [rest.length && hyNoteLink.what(b, rest), notes.length && T("{n} notes", { n: notes.length }), groups.length && T("{n} groups", { n: groups.length })].filter(Boolean).join(", ");
  }
  // every delete says what went, with Undo (P4 B-47: a picture said «went to the archive» without Undo, a note said nothing); one step
  function deleted(before, items, groups, what) {
    const w = what || words(JSON.parse(before), items, groups) || T("1 object");
    commit(before, tr => T("Deleted: {what}", { what: w }) + (tr.gone ? " · " + T("{n} pictures went to the archive", { n: tr.gone }) : ""),
      { key: "del", actions: [{ label: T("Undo"), fn: () => { if (past[past.length - 1] === before) undo(); } }] });
  }
  window.hySel = { carry, pick, tops, clone, holds, words, deleted };
  // one question before something big happens, the app's own dialog, not the system's (P4 B-57): ui/confirm.js ask
  window.hyAsk = async o => (await import(new URL("confirm.js", SRC).href)).ask({ cancel: T("Cancel"), ...o });
  // a command that has nothing to act on says why, in one short note that the next one replaces (P4 B-48: ⌘D, ⌘G, ⌥A on a group,
  // ⇧C with several cards, F on a note did nothing and said nothing)
  window.hyWhy = text => { if (typeof toast === "function") toast(text, "info", { key: "why" }); return false; };
})();
