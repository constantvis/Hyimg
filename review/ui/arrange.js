// «Arrange ›» on the board (owner 2026-10-09: «Что у нас с нашим Arrange? Почему у меня нет кнопок для Arrange новых, которые мы
// разработали, вот эта вся система, которую мы сделали, плюс система, как агент будет расставлять контент: сетка, таблица, вот это вот
// все. Где это все? Почему я не вижу этого?»). Everything the board's layout system does, for the owner, with the agents' own logic:
//   Tidy             As a square block ⌥A, In a row ⌥S, Tidy ⌥D (canvas.html tidy, tidyRow, smartTidy)
//   Grid & table     Make grid, Remove grid (ui/grid.js); Make table: grids.py op_table on the server, a heading row and column
//   Layout patterns  the ten of «Agent layouts» (review/patterns.py): the server runs the agent's own command on the selection
//                    (POST /api/arrange, review/arrange.py) and the page comes back as one undo step
// Where: the right click's «Arrange ›» (canvas.html asks hyGrid.entry and hyGrid.act, they ask this), the layouts button after ⌥A ⌥S ⌥D
// on the bar over a selection (the same menu), and the shortcuts panel (?). Grey rows say why (hyMenuOff). No keys of its own: ⌥A ⌥S ⌥D
// stay the only ones.
(() => {
  // [op, icon, the name on the «Agent layouts» card, the note's title]: the catalogue's order (patterns.py CATALOGUE, p01 … p10)
  const LAYOUTS = [["variants", "layoutVariants", "Variants grid", "Variants"], ["ab", "layoutAB", "A / B", "A / B"],
    ["timeline", "layoutTimeline", "Timeline + batches", ""], ["directions", "layoutDirections", "Direction rows", "Directions"],
    ["docs", "layoutDocs", "Documentation", "Documentation"], ["before-after", "layoutBeforeAfter", "Before / after", "Before / after"],
    ["moodboard", "layoutMoodboard", "Moodboard cluster", "Moodboard"], ["review", "layoutReview", "Review board", "Review"],
    ["flow", "layoutFlow", "Process / flow", ""], ["glossary", "layoutGlossary", "Glossary cards", "Glossary"]];
  const TWO = () => T("Select two or more pictures or cards");
  const it = (attrs, icon, label, keys, why) => hyMenuItem(`data-act="garr" ${attrs}`, icon, label, keys, why ? hyMenuOff(why) : "");
  const esc = v => String(v ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  // what Arrange lays out: pictures, videos, PDFs, plugins' cards (a group: its members); notes, headings and timelines keep their place
  const arrOk = x => !!x && x.type !== "note" && x.type !== "text" && x.type !== "timeline" && (!x.type || x.w > 0) && x.x != null;
  const pick = ids => [...new Set(ids.flatMap(id => board.groups[id] ? board.groups[id].members : [id]))].filter(id => board.items[id]);
  const steps = ids => ids.filter(id => board.groups[id] || (board.items[id] && board.items[id].x != null));
  const tls = () => Object.entries(board.items).filter(([, x]) => x.type === "timeline");

  function entry(ids) {
    const all = pick(ids), pics = all.filter(id => arrOk(board.items[id]));
    if (!pics.length && steps(ids).length < 2) return null;
    const two = pics.length >= 2 ? "" : TWO(), gs = [...new Set(all.map(id => hyGrid.of(board, id)).filter(Boolean))];
    const one = gs.length === 1 && board.grids[gs[0]], table = one && one.head && one.head.row && one.head.col && pics.every(id => one.members.includes(id));
    const sub = () => [it('data-how="grid"', "tidyBlock", T("As a square block"), ["⌥", "A"], two),
      it('data-how="row"', "tidyRow", T("In a row"), ["⌥", "S"], two), it('data-how="smart"', "tidy", T("Tidy"), ["⌥", "D"], two), `<div class="sep"></div>`,
      it('data-how="make"', "gridMake", T("Make grid"), null, hyGrid.placed(board, all).length >= 2 ? "" : TWO()),
      it('data-how="table"', "table", T("Make table"), null, two || (table ? T("This is a table already") : "")),
      it('data-how="remove"', "gridRemove", T("Remove grid"), null, gs.length ? "" : T("Not in a grid")), `<div class="sep"></div>`,
      hyMenuSub('data-sub="layouts"', "layouts", T("Layout patterns"), () => layouts(ids, pics))].join("");
    return Object.assign(["arrange", "tidyBlock", T("Arrange")], { sub });
  }
  function layouts(ids, pics) {
    return LAYOUTS.map(([op, icon, name]) => {
      const a = `data-how="pattern" data-op="${op}" data-name="${esc(name)}"`;
      if (op === "timeline") {
        const why = !tls().length ? T("Put a timeline on the page first: L") : !pics.length ? T("Select pictures or cards") : "";
        return why ? it(a, icon, T(name), null, why) : hyMenuSub(`data-sub="phases"`, icon, T(name), phases);
      }
      return it(a, icon, T(name), null, op === "flow" ? (steps(ids).length >= 2 ? "" : T("Select two or more things to join")) : pics.length >= 2 ? "" : TWO());
    }).join("");
  }
  function phases() {   // the phases of the page's timelines: the batch goes under the one picked, «New phase» right of the last
    return tls().map(([tl, x], k) => (k ? `<div class="sep"></div>` : "") + [...x.points].sort((p, q) => p.t - q.t).map((p, n) =>
      it(`data-how="pattern" data-op="timeline" data-tl="${tl}" data-ph="${esc(p.id)}" data-name="${esc(p.text || T("Phase {n}", { n: n + 1 }))}"`,
        "layoutTimeline", esc(p.text || T("Phase {n}", { n: n + 1 })))).join("")
      + it(`data-how="pattern" data-op="timeline" data-tl="${tl}" data-ph="" data-name="${esc(T("Phase {n}", { n: x.points.length + 1 }))}"`,
        "plus", T("New phase"))).join("");
  }

  function act(b, ids) {
    if (b.dataset.act !== "garr") return false;
    const how = b.dataset.how, all = pick(ids);
    if (how === "grid" || how === "row" || how === "smart") { sel = new Set(all); ({ grid: tidy, row: tidyRow, smart: smartTidy })[how](); return true; }
    if (how === "make") {
      const before = HY.snap(), gid = hyGrid.make(board, all, null, false, HY.uid), g = gid && board.grids[gid];
      if (g) HY.commit(before, T("Grid {c} × {r}", { c: Math.min(g.cols, g.members.length), r: g.rows }));
    }
    if (how === "remove") {
      const before = HY.snap();
      new Set(all.map(id => hyGrid.of(board, id)).filter(Boolean)).forEach(g => delete board.grids[g]);
      if (!Object.keys(board.grids).length) delete board.grids;
      HY.commit(before, T("Grid removed, everything stays where it is"));
    }
    if (how === "table") run("table", all, { title: T("Table") }, T("Table"));
    if (how === "pattern") {
      const op = b.dataset.op, name = T(b.dataset.name), opt = { color: typeof pref === "function" ? pref("notecolor", "yellow") : "yellow" };
      const title = (LAYOUTS.find(l => l[0] === op) || [])[3]; if (title) opt.title = T(title);
      if (op === "before-after") Object.assign(opt, { before: T("Before"), after: T("After") });
      if (op === "review") Object.assign(opt, { picked: T("Picked"), decide: T("To decide"), rejected: T("Rejected") });
      if (op === "timeline") Object.assign(opt, { tl: b.dataset.tl, phase: b.dataset.ph || b.dataset.name, title: b.dataset.name });
      run(op, op === "flow" ? steps(ids) : all, opt, name);
    }
    return true;
  }
  // the server lays the selection out with the agents' command; the page comes back and is one undo step (nothing else changed meanwhile)
  async function run(op, ids, opt, name) {
    const before = HY.snap(), page = JSON.parse(before); delete page.sel;
    let r, d = {};
    const body = JSON.stringify({ board: page, op, sel: ids, opt });
    try { r = await fetch("/api/arrange", { method: "POST", headers: { "Content-Type": "application/json" }, body }); d = await r.json(); }
    catch (e) { HY.toast(T("Could not lay it out: the server did not answer"), "error"); return; }
    if (!r.ok) { HY.toast(T("Could not lay it out: {why}", { why: d.error || r.status }), "error"); return; }
    if (HY.snap() !== before) { HY.toast(T("The board changed meanwhile: lay it out again"), "error"); return; }
    const o = d.board; board.items = o.items; board.groups = o.groups; board.grids = o.grids; board.links = o.links; board.removed = o.removed || {};
    sel = new Set(d.sel.filter(i => board.items[i] || board.groups[i]));
    api.last = { op, cmd: d.cmd, log: d.log, board: JSON.parse(JSON.stringify(o)) };   // as the server laid it out, before the board draws it
    HY.commit(before, T("Laid out: {name}", { name }));
  }

  // the bar over a selection: ⌥A ⌥S ⌥D, then the button that opens this same menu under it
  const bar = () => `<button class="ic" data-tidy="grid" title="${T("As a square block · ⌥A")}" aria-label="${T("Arrange")}">${hyIcon("tidyBlock", 15, 2)}<kbd>⌥A</kbd></button>`
    + `<button class="ic" data-tidy="row" title="${T("In one row, aligned at the top · ⌥S")}" aria-label="${T("In a row")}">${hyIcon("tidyRow", 15, 2)}<kbd>⌥S</kbd></button>`
    + `<button class="ic" data-tidy="smart" title="${T("Tidy: rows and blocks stay, the gaps become even · ⌥D")}" aria-label="${T("Tidy")}">${hyIcon("tidy", 15, 2)}<kbd>⌥D</kbd></button>`
    + `<button class="ic" data-arrange title="${T("Arrange: grid, table, layout patterns")}" aria-label="${T("Arrange")}" aria-haspopup="menu">${hyIcon("layouts", 15, 2)}</button>`;
  function open(btn) {
    const ids = [...sel], e = entry(ids), m = document.getElementById("ctx"); if (!e || !m) return;
    m.innerHTML = e.sub();
    m.onclick = ev => { const b = ev.target.closest("[data-act]"); if (!b || b.getAttribute("aria-disabled") === "true") return; ctxClose(); act(b, ids); };
    m.classList.add("open");
    const r = btn.getBoundingClientRect(), w = m.offsetWidth, h = m.offsetHeight;
    m.style.left = Math.max(8, Math.min(r.left, innerWidth - w - 8)) + "px";
    m.style.top = (r.bottom + 6 + h > innerHeight - 8 ? Math.max(8, r.top - 6 - h) : r.bottom + 6) + "px";
  }
  // opened after the press has run its course: the board closes its menu on any press and draws the bar again
  const btn = e => e.target.closest && e.target.closest(".tidy [data-arrange]");
  const later = () => setTimeout(() => { const b = document.querySelector("#handles .tidy [data-arrange]"); if (b) open(b); });
  document.addEventListener("pointerdown", e => { if (btn(e) && e.button === 0) later(); }, true);
  document.addEventListener("click", e => { if (btn(e) && e.detail === 0) later(); });   // Enter or Space on the button

  // the shortcuts panel (?): where Arrange's rows are, after ⌥D
  function keys() {
    const k = document.getElementById("keys"); if (!k || k.querySelector("[data-arrange-keys]")) return;
    const after = [...k.children].find(d => /⌥\s*D/.test(d.querySelector(".k")?.textContent || "")) || k.lastElementChild;
    const row = (what, how) => `<div data-arrange-keys><span class="k">${what}</span> ${how}</div>`;
    after.insertAdjacentHTML("afterend", row(T("right click › Arrange"), T("Make grid, Make table, Remove grid"))
      + row(T("Arrange › Layout patterns"), LAYOUTS.map(l => T(l[2])).join(", "))
      + row(`${hyIcon("layouts", 13, 2)} ${T("on the bar")}`, T("the same menu for the selection")));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", keys); else keys();

  const api = window.hyArrange = { entry, act, bar, open, layouts: LAYOUTS.map(l => l[0]), last: null };
})();
