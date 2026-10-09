// The board's side of merged saves (owner 2026-10-08: «Две правки одной доски с двух Маков могут перезаписать друг друга. Сделать
// слияние по объектам? — да»). The server merges a save with the file object by object (review/merge.py) and answers with what it
// wrote; this page then puts the edits made here since the save left back on top of that, so a drag, the selection and the camera
// stay. The same merge takes another writer's version while edits here wait to be saved (the live board, canvas.html pullRemote).
// Here the edits of this page always win: they are the newest and are saved next, where the server decides by time.
(() => {
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const META = new Set(["revision", "saved", "vid", "parent", "edited", "by", "schema"]), MAPS = ["items", "groups", "grids", "links", "removed"];
  const FIELD = { x: "position", y: "position", w: "size", h: "size" };
  const sorted = v => v && typeof v === "object" && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(k => [k, v[k]])) : v;
  const canon = v => JSON.stringify(v, (_, x) => sorted(x));
  const same = (a, b) => a === b || (a !== undefined && b !== undefined && (JSON.stringify(a) === JSON.stringify(b) || canon(a) === canon(b)));

  // the keys in draw order: ours when ours reordered what all three had, else theirs; the other side's new ones after (merge.py order)
  function order(b, l, r) {
    const both = Object.keys(b).filter(k => k in l && k in r), mine = Object.keys(l).filter(k => k in b && k in r);
    const [a, c] = mine.join("\n") !== both.join("\n") ? [l, r] : [r, l];
    return [...new Set([...Object.keys(a), ...Object.keys(c)])];
  }
  function fields(...ds) {
    const out = new Map();
    for (const d of ds) for (const k of Object.keys(d)) { const f = FIELD[k] || k; if (!out.has(f)) out.set(f, []); if (!out.get(f).includes(k)) out.get(f).push(k); }
    return out;
  }
  // a group's members as sets: what either side added, minus what either side took out (a grid's too, in this side's order)
  function members(b = [], l = [], r = []) {
    const gone = new Set([...b].filter(m => !l.includes(m) || !r.includes(m)));
    return [...new Set([...l, ...r])].filter(m => !gone.has(m));
  }
  // one item or group: whole when one side changed it, else field by field, this page's field when it changed it
  function thing(b, l, r, group) {
    if (l === undefined || r === undefined) {
      const here = l === undefined ? r : l;
      if (here === undefined || b === undefined) return here;   // added on one side
      return same(here, b) ? undefined : here;                   // deleted there: gone if untouched here, else it stays
    }
    if (same(l, r)) return l;
    b = b || {};
    if (same(l, b)) return r;
    if (same(r, b)) return l;
    const out = {};
    for (const [f, keys] of fields(l, r, b)) {
      if (f === "members" && group) { out.members = members(b.members, l.members, r.members); continue; }
      const from = same(keys.map(k => l[k]), keys.map(k => b[k])) ? r : l;
      for (const k of keys) if (from[k] !== undefined) out[k] = from[k];
    }
    return out;
  }
  function map(b = {}, l = {}, r = {}, kind) {
    const out = {};
    for (const k of order(b, l, r)) {
      const v = kind === "removed" ? (same(l[k], b[k]) ? r[k] : l[k]) : thing(b[k], l[k], r[k], kind === "groups" || kind === "grids");
      if (v !== undefined && v !== null) out[k] = v;
    }
    return out;
  }
  // base: the version local started from; local: this page's board; remote: the other version. The result has remote's revision.
  function merge3(base, local, remote) {
    const b = base || {}, out = { ...remote };
    for (const k of new Set([...Object.keys(local), ...Object.keys(remote)])) {
      if (META.has(k) || MAPS.includes(k)) continue;
      const v = same(local[k], b[k]) ? remote[k] : local[k];
      if (v === undefined) delete out[k]; else out[k] = v;
    }
    for (const k of MAPS) if ((k !== "grids" && k !== "links") || b[k] || local[k] || remote[k]) out[k] = map(b[k] || {}, local[k] || {}, remote[k] || {}, k);
    if (out.grids && window.hyGrid) hyGrid.merged(out, local, remote);   // a grid edited on both sides: one grid again (ui/grid.js)
    if (out.links && window.hyConn) hyConn.prune(out);   // an arrow to a thing the other side deleted goes (ui/connectors.js)
    return out;
  }
  const whoOf = by => (window.hyWhoText ? window.hyWhoText({ by }) : "") || (by && by.via && by.via !== "app" ? by.via : "");
  // A merged save, quietly (owner 2026-10-09 on r12/docs-merge.html, version 6 «Pick: 2 + 3 + 5»: «6 версия отличная»). Until then a
  // toast came with every merged save, again and again while an agent wrote (owner 2026-10-08: «когда они так крутят, они начинают
  // немного надоедать»). Now: what the other side changed glows in its author's colour with the author's name on it for 2 s; the
  // author's face slides into the top row by History for 3 s and History keeps a dot in that colour until it is opened, pointing at
  // it says who and how much; a toast only for a clash, the same field changed on both sides, with Show. Nothing else speaks: the
  // merge itself is in History › Activity as before. ctx (canvas.html applyMerged): sent, the board this page saved; board, what the
  // server wrote; rect(id), a thing's box on the board; show(ids), select them and bring them into view.
  // who, short: this Mac's own agent by its name alone («Claude»), anyone else as History says it («Codex · Ann», «Ann»)
  const short = by => { const w = window.hyWhoOf ? window.hyWhoOf(by) : null; return (w && w.me && w.via) || whoOf(by) || T("Someone"); };
  const look = by => {
    const w = window.hyWhoOf ? window.hyWhoOf(by) : null, k = window.HY_AGENTS ? HY_AGENTS.kind(by && by.via) : "";
    return { text: short(by), color: (w && w.color) || `var(--hy-ag-${k || "agent"})` };
  };
  // a thing by what the board shows of it now: a note's or a heading's first line, a group's title, a file's name
  const nameOf = (id, board, c) => {
    const it = board && ((board.items || {})[id] || (board.groups || {})[id]) || {};
    const t = String(it.text || it.title || it.label || "").split("\n").map(x => x.trim()).find(Boolean) || "";
    return (t.length > 40 ? t.slice(0, 39) + "…" : t) || (it.path ? String(it.path).split("/").pop() : "") || c.text
      || (c.path ? String(c.path).split("/").pop() : "") || (WORD[c.field] ? T(WORD[c.field]) : c.field);
  };
  const plain = v => { if (!v || typeof v !== "object") return v; const { by, ...rest } = v; return rest; };   // a note's author the server kept is no change
  // the things the other side changed: what the server wrote differs from what this page sent, or is new; and what it deleted
  function changed(sent, board) {
    const ids = [], gone = [];
    for (const k of ["items", "groups"]) {
      const a = (sent && sent[k]) || {}, b = (board && board[k]) || {};
      for (const id of Object.keys(b)) if (!same(plain(a[id]), plain(b[id]))) ids.push(id);
      for (const id of Object.keys(a)) if (!(id in b)) gone.push(id);
    }
    return { ids, gone };
  }
  function css() {
    if (document.getElementById("hyMergeCss")) return;
    const l = document.createElement("link"); l.id = "hyMergeCss"; l.rel = "stylesheet"; l.href = new URL("merge.css", SRC).href; document.head.appendChild(l);
  }
  // the things ringed in a colour on the board, the name over each (cls "warn": Show's amber ring, no name); 60 at most
  function glow(ids, who, ctx, ms = 2200, cls = "") {
    const world = document.getElementById("world"); if (!world || !ctx || !ctx.rect) return;
    let layer = document.getElementById("hyMergeGlow");
    if (!layer) { layer = document.createElement("div"); layer.id = "hyMergeGlow"; layer.setAttribute("aria-hidden", "true"); world.appendChild(layer); }
    for (const id of ids.slice(0, 60)) {
      const r = ctx.rect(id); if (!r || ![r.x, r.y, r.w, r.h].every(Number.isFinite)) continue;
      layer.querySelectorAll(".hy-mg").forEach(x => { if (x.dataset.id === id) x.remove(); });
      const el = document.createElement("div"); el.className = "hy-mg" + (cls ? " " + cls : ""); el.dataset.id = id;
      Object.assign(el.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px" }); el.style.setProperty("--mg", who.color);
      if (who.text) { const t = document.createElement("span"); t.className = "hy-mgt"; t.textContent = who.text; el.appendChild(t); }
      layer.appendChild(el); requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("on")));
      setTimeout(() => { el.classList.remove("on"); setTimeout(() => el.remove(), 600); }, ms);
    }
  }
  // the author's face by History for 3 s: «?» and the bell step aside while it is there (ui/merge.css)
  function face(by, who) {
    const h = document.getElementById("bhist"); if (!h) return;
    let f = document.getElementById("hyMergeFace");
    if (!f) { f = document.createElement("hy-plate"); f.id = "hyMergeFace"; f.className = "hy-mface"; f.setAttribute("data-hyui", ""); h.before(f); }
    f.innerHTML = window.hyAvatarOf ? hyAvatarOf(by, 24) : ""; f.title = who.text; f.style.setProperty("--mg", who.color);
    const de = document.documentElement; de.classList.add("hy-mface-on");
    clearTimeout(face.t); face.t = setTimeout(() => de.classList.remove("hy-mface-on"), 3000);
  }
  // History's dot until History is opened; pointing at History says who and how many things since the dot came
  const DOT = { n: 0, who: "", t: 0 };
  function dot(who, n) {
    const h = document.getElementById("bhist"); if (!h) return;
    if (!h.querySelector(".hy-mdot")) {
      h.insertAdjacentHTML("beforeend", '<span class="hy-mdot"></span><span class="hy-mhv" role="tooltip"></span>');
      h.addEventListener("click", () => { h.classList.remove("hy-mdot-on"); DOT.n = 0; if (h.dataset.mTitle) { h.title = h.dataset.mTitle; delete h.dataset.mTitle; } }, true);
      h.addEventListener("pointerenter", () => { const v = h.querySelector(".hy-mhv"); if (v && DOT.n) v.textContent = words(); });
    }
    DOT.n += Math.max(1, n); DOT.who = who.text; DOT.t = Date.now(); h.style.setProperty("--mg", who.color);
    if (!h.dataset.mTitle) h.dataset.mTitle = h.title || "";
    h.title = ""; h.classList.add("hy-mdot-on"); h.querySelector(".hy-mhv").textContent = words();
  }
  const words = () => T("{who} merged {n} changes", { who: DOT.who, n: DOT.n }) + " · " + (T.ago ? T.ago(DOT.t) : "");
  // a clash: one toast for the save, in amber; Show brings the things into view and rings them amber for a moment
  function clash(cs, toast, ctx) {
    const ids = [...new Set(cs.map(c => c.id).filter(Boolean))], c = cs[0];
    const who = short(c.kept === "theirs" ? c.kept_by : c.lost_by), what = nameOf(c.id, ctx && ctx.board, c);
    const text = ids.length > 1 ? T("You and {who} both changed {n} things: the newer changes are kept, the others are in History", { who, n: ids.length })
      : c.kept === "theirs" ? T("You and {who} changed «{what}»: theirs is kept", { who, what }) : T("You and {who} changed «{what}»: yours is kept", { who, what });
    const shown = () => ids.filter(id => ctx && ctx.rect && ctx.rect(id));
    const show = () => { const on = shown(); if (!on.length) return; if (ctx.show) ctx.show(on); glow(on, { text: "", color: "var(--ht-warn)" }, ctx, 1600, "warn"); };
    (toast || window.hyToast || console.log)(text, "warn", ctx && ctx.rect ? { actions: [{ label: T("Show"), fn: show }] } : undefined);
  }
  function tell(info, toast, ctx) {
    if (!info) return;
    const from = (info.from || []).filter(b => b && typeof b === "object"), cs = info.conflicts || [];
    const ch = ctx && ctx.board ? changed(ctx.sent, ctx.board) : { ids: [], gone: [] };
    const by = from[0] || (cs[0] && (cs[0].kept === "theirs" ? cs[0].kept_by : cs[0].lost_by)) || null;
    if (by && (from.length || ch.ids.length || ch.gone.length)) {
      css(); const who = look(by);
      if (from.length > 1) who.text = [...new Set(from.map(short))].join(", ");
      glow(ch.ids, who, ctx); face(by, who); dot(who, ch.ids.length + ch.gone.length);
    }
    if (cs.length) { css(); clash(cs, toast, ctx); }
  }
  // History › Events: a merged save that changed the same thing on both sides, a Dropbox copy merged
  const WORD = { position: "Position", size: "Size", text: "Text", color: "Colour", title: "Title", deleted: "Deleted on one side", members: "Members" };
  const prev = window.hyEvView;
  window.hyEvView = (e, esc) => {
    if (e.kind !== "merge" && e.kind !== "dropbox") return prev ? prev(e, esc) : null;
    const rows = (e.conflicts || []).slice(0, 6).map(c => `<div class="em">${esc(T("{what}: kept the change by {who}",
      { what: WORD[c.field] ? T(WORD[c.field]) : c.field, who: whoOf(c.kept_by) || T("Someone") }))}${c.text ? " · " + esc(c.text) : ""}</div>`);
    const file = e.kind === "dropbox" && e.file ? `<div class="em">${esc(e.file)}</div>` : "";
    return [T(e.kind === "dropbox" ? "Dropbox copy merged" : "Changes merged"), file + rows.join("")];
  };
  window.hyMerge = { merge3, tell, members, same, changed };
})();
