// The numbers on the cells of a choice grid (owner 2026-10-09, «Agent layouts» p01 «Variants grid»: «owner answers by numbers: 2, 7»;
// the rules card: «numbers on choices»). A grid a layout pattern made for a choice (review/patterns.py) carries "num"; each of its
// pictures and cards shows its number as a mark in its top left corner, the marks' plate and size, under the note dots when it has
// them. Headings in the grid (a table's titles, a direction's label) are not numbered. The modes, as patterns.py writes them:
//   seq  1 … N in reading order                       (variants, a phase's batch, documentation)
//   rc   the column's letter and the row: A1, B1 …    (A / B: the letter is the column title's first word)
//   row  the row: 1 1, 2 2 …                          (before / after)
//   col  the place in its row: 1 2 3 …                (directions, each row headed by its label)
// hy.py map and md show the same numbers (grids.py tables); ui/connectors.js calls paint() at the end of each renderLinks pass.
(() => {
  let done = new Map();   // id -> the number it shows
  function labels(b) {
    const out = new Map(), G = b.grids || {}, text = id => (b.items[id] || {}).type === "text";
    for (const gid in G) {
      const g = G[gid]; if (!g.num) continue;
      const ms = (g.members || []).filter(m => b.items[m]), cols = Math.max(1, Math.min(g.cols || 1, ms.length || 1)), rows = [];
      for (let k = 0; k < ms.length; k += cols) rows.push(ms.slice(k, k + cols));
      const headRow = rows.length > 1 && rows[0].every(text) ? 1 : 0;
      const letter = c => { const t = headRow ? ((b.items[rows[0][c]] || {}).text || "").trim().split(/[\s·]+/)[0] : ""; return t && t.length <= 3 ? t : "ABCDEFGH"[c] || ""; };
      let n = 0;
      rows.forEach((r, ri) => {
        if (ri < headRow) return; let inRow = 0;
        r.forEach((m, c) => {
          if (text(m)) return; n++; inRow++;
          out.set(m, g.num === "rc" ? letter(c) + (ri - headRow + 1) : g.num === "row" ? String(ri - headRow + 1) : g.num === "col" ? String(inRow) : String(n));
        });
      });
    }
    return out;
  }
  function paint() {
    if (typeof board === "undefined" || typeof EL === "undefined") return;
    const want = labels(board);
    for (const [id, lab] of want) {
      const el = EL.get(id); if (!el) continue;
      let s = el.querySelector(":scope > .mk-num");
      if (!s) { s = document.createElement("span"); s.className = "mk mk-tl mk-num"; el.appendChild(s); }
      if (s.textContent !== lab) s.textContent = lab;
    }
    for (const id of done.keys()) if (!want.has(id)) { const s = EL.get(id) && EL.get(id).querySelector(":scope > .mk-num"); if (s) s.remove(); }
    done = want;
  }
  window.hyGridNum = { labels, paint };
})();
