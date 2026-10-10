// ⌘Z after someone else's edit (P4 B-06, П4 audit 2026-10-10: an agent's write to the board took the whole undo history away). An undo
// step is the board as it was (canvas.html past / future, one JSON string each). A version from elsewhere (an agent, another Mac, a
// merged save) changes the board under the steps; until now they were all dropped then. Now each such change is kept as a small delta,
// only the things it touched as they were and as they are, and a step is brought up to date when ⌘Z or ⇧⌘Z takes it: thing by thing and
// field by field as hyMerge's merge decides, the other side's change wins, and what it deleted stays deleted. So ⌘Z undoes only your own
// work. A step that has nothing of yours left to undo (the other side changed the same thing) is skipped, and the toast says so.
//   hyUndo.seen(was, now)       canvas.html adopt: the board before and after a version from elsewhere
//   hyUndo.take(stack, cur)     the next step of past or future brought up to date, [string, the string as it was pushed]; [] when none
(() => {
  if (window.hyUndo) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)));
  const MAPS = ["items", "groups", "grids", "links", "removed"], PAGES = {};
  const clone = v => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
  // a page's deltas (log) and how many of them each step still waiting in past or future has seen (at); a step not in at has seen all
  const page = () => PAGES[BOARD] || (PAGES[BOARD] = { log: [], at: new Map() });
  function seen(was, now) {
    const P = page(), steps = [...past, ...future];
    if (!steps.length) { P.log = []; P.at = new Map(); return; }
    const d = {}; let n = 0;
    for (const m of MAPS) {
      const a = (was && was[m]) || {}, b = (now && now[m]) || {};
      for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
        if (!hyMerge.same(a[k], b[k])) { (d[m] || (d[m] = {}))[k] = [clone(a[k]), clone(b[k])]; n++; }
      }
    }
    if (!n) return;
    const at = new Map(); for (const s of steps) at.set(s, P.at.has(s) ? P.at.get(s) : P.log.length);   // only the steps still there
    const low = Math.min(...at.values()); P.log = P.log.slice(low); at.forEach((v, s) => at.set(s, v - low));   // what no step needs goes
    P.at = at; P.log.push(d);
  }
  // one delta onto a step's board o: theirs (l) against what the step holds (r), from what was (b)
  function apply(o, d) {
    for (const m of MAPS) {
      const ch = d[m]; if (!ch) continue;
      const t = o[m] || (o[m] = {});
      for (const [k, [b, l]] of Object.entries(ch)) {
        const v = m === "removed" || l === undefined ? l : hyMerge.thing(b, l, t[k], m === "groups" || m === "grids");
        if (v === undefined || v === null) delete t[k]; else t[k] = clone(v);
      }
      if ((m === "grids" || m === "links") && !Object.keys(t).length) delete o[m];
    }
    if (window.hyConn) hyConn.prune(o);   // an arrow to a thing the other side deleted goes
  }
  const differs = (o, cur) => MAPS.some(m => !hyMerge.same(o[m] || {}, cur[m] || {}));
  function take(stack, cur) {
    const P = page(); let skipped = 0, out = [];
    while (stack.length) {
      const orig = stack.pop(), from = P.at.has(orig) ? P.at.get(orig) : P.log.length;
      if (from >= P.log.length) { out = [orig, orig]; break; }
      const o = JSON.parse(orig);
      P.log.slice(from).forEach(d => apply(o, d));
      if (!differs(o, cur)) { skipped++; continue; }
      out = [JSON.stringify({ items: o.items, groups: o.groups, removed: o.removed, grids: o.grids, links: o.links, sel: o.sel }), orig]; break;
    }
    if (skipped && typeof toast === "function") toast(T("Undo steps skipped: {n}, someone changed the same things since", { n: skipped }), "info");
    return out;
  }
  window.hyUndo = { seen, take };
})();
