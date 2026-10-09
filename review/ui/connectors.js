// Arrows between anything on the board (owner 2026-10-09 on «Agent layouts» › 4 Structures and the «Board structure» card «Arrows
// between anything»: «реализуй это»; st6 «A, then C»: arrows from any object with the notes' soft curve, labels and dashes now).
// A note's arrow says what the note is about and stays the note's (ui/notelink.js); a connector says how two things relate, from any
// thing to any other: a picture, a card, a heading, a group, a note, a timeline. board.links[id] = { from, to, label?, style?: dashed |
// dotted, color?: blue }, the same record review/connectors.py keeps for hy.py and merge.py merges by id.
//
// Drawn as the notes' arrows are (a69dc0b, 0cf175e): a soft curve from the side of one that faces the other, a small dot where it
// starts and a head on the other's edge, the line under the cards it crosses (notelink.js underCut), sizes on screen by --z; hovered
// 3 px with a × under the pointer that rides along the line (notelink.js moves any #links .arw .del.m), a click on it takes the arrow
// off («Arrow removed», Undo, ⌘Z). Its label sits on the middle of the curve, a pill of constant size on screen; a click on it edits
// the words, the line (solid «is», dashed «like», dotted «maybe») and the colour (blue «picked»). An arrow with no words shows a
// «+ Label» pill while one of its ends is selected.
// Made by a drag from the round handle on the right side of one selected thing (a note keeps its own handle: its arrow is a note's
// link) to any other thing or group; the thing under the pointer is outlined while it is pulled. canvas.html calls hyConn.svg in
// renderLinks, hyConn.handle in renderHandles, hyConn.prune in commit; snap and restore carry board.links.
(() => {
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL("connectors.css", SRC).href; document.head.appendChild(l); }
  const L = () => window.hyNoteLink;
  const table = b => (b && b.links) || {};
  const there = (b, i) => !!(b.items[i] || b.groups[i]);
  const uidC = () => "c" + Math.random().toString(36).slice(2, 9);
  // a connector whose end left the page goes with it; an empty map goes too (review/connectors.py prune)
  function prune(b) {
    const T = table(b); let n = 0;
    for (const k of Object.keys(T)) { const c = T[k]; if (!c || c.from === c.to || !there(b, c.from) || !there(b, c.to)) { delete T[k]; n++; } }
    if (b.links && !Object.keys(b.links).length) delete b.links;
    return n;
  }
  const pairOf = (b, a, z) => Object.keys(table(b)).find(k => b.links[k].from === a && b.links[k].to === z) || null;
  function add(b, a, z) {
    if (a === z || !there(b, a) || !there(b, z) || pairOf(b, a, z)) return null;
    const id = uidC(); (b.links || (b.links = {}))[id] = { from: a, to: z }; return id;
  }

  // ---- geometry: board units only, the same markup at any zoom ----
  const C = r => ({ x: r.x + r.w / 2, y: r.y + r.h / 2 });
  const nearestSide = (r, p) => [[r.x, p.y, -1, 0], [r.x + r.w, p.y, 1, 0], [p.x, r.y, 0, -1], [p.x, r.y + r.h, 0, 1]]
    .map(([x, y, ux, uy]) => ({ x: Math.min(Math.max(x, r.x), r.x + r.w), y: Math.min(Math.max(y, r.y), r.y + r.h), ux, uy }))
    .sort((p1, p2) => Math.hypot(p1.x - p.x, p1.y - p.y) - Math.hypot(p2.x - p.x, p2.y - p.y))[0];
  function curve(fr, tr, bend) {   // [start, c1, c2, end] and the way the end comes in; bend: A → B beside B → A, each bows to its left
    const { side, holds } = L(), fc = C(fr), tc = C(tr); let b, u, a, au;
    if (holds(tr, fc)) { const e = nearestSide(tr, fc); b = { x: e.x, y: e.y }; u = { x: e.ux, y: e.uy }; }   // from inside it: out to its edge
    else { const e = side(tr, fc); b = { x: e.x, y: e.y }; u = { x: -e.ux, y: -e.uy }; }
    if (holds(fr, tc)) { const s = nearestSide(fr, tc); a = { x: s.x, y: s.y }; au = { x: -s.ux, y: -s.uy }; }   // to a thing inside it
    else { const s = side(fr, b); a = { x: s.x, y: s.y }; au = { x: s.ux, y: s.uy }; }
    const len = Math.hypot(b.x - a.x, b.y - a.y), k = Math.max(24, len * .4), o = bend ? len * .18 : 0, nx = len ? (b.y - a.y) / len : 0, ny = len ? (a.x - b.x) / len : 0;
    return { P: [a, { x: a.x + au.x * k + nx * o, y: a.y + au.y * k + ny * o }, { x: b.x - u.x * k + nx * o, y: b.y - u.y * k + ny * o }, b], u };
  }
  const f = v => Math.round(v * 100) / 100, pt = q => `${f(q.x)} ${f(q.y)}`;
  const deg = v => Math.round(Math.atan2(v.y, v.x) * 1800 / Math.PI) / 10;
  const HL = 11, HW = 5, DR = 9, XG = 10 / 24;   // the head and the × as the notes' arrows have them (notelink.js)
  let measure = null; const widths = new Map();   // the words' width on screen, once per text
  const textW = s => { if (widths.has(s)) return widths.get(s); measure = measure || document.createElement("canvas").getContext("2d");
    measure.font = "500 12px Geist, system-ui, sans-serif"; const w = Math.ceil(measure.measureText(s).width); if (widths.size < 2000) widths.set(s, w); return w; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // hy-allow-begin: icon-inline the board's own drawing, the connectors' curves, heads and label pills; the × is the registry's «close»
  function one(id, c, ends, rev) {
    const fr = rectOf(c.from), tr = rectOf(c.to); if (!fr || !tr) return "";
    const { P, u } = curve(fr, tr, rev), b = P[3], d = `M${pt(P[0])}C${pt(P[1])} ${pt(P[2])} ${pt(b)}`, m = Math.min(tr.w, tr.h, fr.w || 1e9, fr.h || 1e9);
    const on = sel.has(c.from) || sel.has(c.to), cls = `cnx${on ? " on" : ""}${c.color === "blue" ? " blue" : ""}`;
    const cut = L().underCut({ key: c.from + "|" + c.to, cid: "cn-" + id, ends, nr: fr }, P, f);
    const mid = L().bz(P, .5), lab = c.label || "", w = lab ? textW(lab) + 18 : textW(T("+ Label")) + 18;
    let h = `<g class="${cls}" data-c="${id}"><g class="arw cn-arw${c.style === "dashed" ? " ds" : c.style === "dotted" ? " dt" : ""}" data-k="${c.from}|${c.to}"`
      + ` style="--rmax:${f(Math.max(1, m * .02))}px;--hmax:${f(Math.max(.05, m * .3 / HL))}">`
      + (cut ? `<g${cut}>` : "") + `<path class="hit" data-conn="${id}" d="${d}" fill="none" stroke="transparent"/><path class="ln" d="${d}" fill="none" stroke-linecap="butt"/>`
      + (cut ? "</g>" : "") + `<circle class="c0" cx="${f(P[0].x)}" cy="${f(P[0].y)}"/>`
      + `<g transform="translate(${pt(b)}) rotate(${deg(u)})"><polygon class="hh" points="0 0 ${-HL} ${HW} ${-HL} ${-HW}"/></g>`
      + `<g class="del m" data-conndel="${id}" transform="translate(${pt(mid)})"><g class="xs"><title>${esc(T("Remove arrow"))}</title>`
      + `<circle r="${f(DR / XG)}" stroke-width="${f(2 / XG)}"/><path transform="translate(-12 -12)" d="${hyIconPath("close")}" stroke-width="${f(1.9 / XG)}" stroke-linecap="round"/></g></g></g>`;
    const len = Math.hypot(b.x - P[0].x, b.y - P[0].y);   // far out the pill shrinks with its arrow: at most 60 % of the arrow's length wide
    h += `<g class="clab${lab ? "" : " empty"}" data-clab="${id}" transform="translate(${pt(mid)})" style="--lmax:${f(Math.max(.01, len * .6 / w))}">`
      + `<g class="cls"><title>${esc(T("Arrow: words, line, colour"))}</title>`
      + `<rect x="${-w / 2}" y="-11" width="${w}" height="22" rx="11"/><text text-anchor="middle" y="4.2">${esc(lab || T("+ Label"))}</text></g></g>`;
    return h + "</g>";
  }
  // hy-allow-end
  // canvas.html renderLinks: every connector, the arrow being pulled (a note's or a connector's), the numbers of choice grids
  // hy-allow-begin: icon-inline the board's own drawing, the dashed line of an arrow being pulled
  function svg(ends, drag) {
    let h = "";
    const T_ = table(board), K = new Set(Object.values(T_).map(c => c.from + "|" + c.to));
    for (const id in T_) h += one(id, T_[id], ends, K.has(T_[id].to + "|" + T_[id].from));
    if (drag && drag.mode === "connect" && drag.cur) {   // a note's arrow being pulled (moved here from canvas.html)
      const a = edgePt(rectOf(drag.id), drag.cur);
      h += `<line class="lkd" x1="${a.x}" y1="${a.y}" x2="${drag.cur.x}" y2="${drag.cur.y}" stroke="${noteCol(board.items[drag.id])[0]}"/>`;
    }
    if (pull && pull.cur) { const a = edgePt(rectOf(pull.id), pull.cur); h += `<line class="lkd cnd" x1="${a.x}" y1="${a.y}" x2="${pull.cur.x}" y2="${pull.cur.y}"/>`; }
    if (window.hyGridNum) hyGridNum.paint();
    return h;
  }
  // hy-allow-end

  // ---- the handle and the drag ----
  // canvas.html renderHandles: one thing selected, not a note (its own handle makes a note's link) and not a timeline's dot
  function handle(h, id, r) {
    const it = board.items[id]; if (it && it.type === "note") return;
    if (!handlesOn(r.w * cam.z, r.h * cam.z)) return;
    const cn = document.createElement("div"); cn.className = "cn cc"; cn.dataset.cc = id; cn.title = T("Drag to anything: an arrow");
    Object.assign(cn.style, { left: r.x + r.w + "px", top: r.y + r.h / 2 + "px" }); h.appendChild(cn);
  }
  let pull = null;   // { id, before, cur, target }
  const outline = (el, on) => { if (!el) return; el.classList.toggle("linktarget", on); if (on) el.style.setProperty("--lt", "var(--sel)"); else el.style.removeProperty("--lt"); };
  const dropAt = (x, y, from) => document.elementsFromPoint(x, y).find(el => el.matches && el.matches(".it, .plg, .tx, .tl, .grp, .note") && el.dataset.id
    && el.dataset.id !== from && (el.classList.contains("grp") ? !!board.groups[el.dataset.id] : !!board.items[el.dataset.id]));
  document.addEventListener("pointerdown", e => {
    if (ed && !ed.el.contains(e.target)) close();   // a click anywhere else applies the editor's words
    if (e.button !== 0) return;
    const del = e.target.closest && e.target.closest("[data-conndel]");
    if (del) { e.stopPropagation(); e.preventDefault(); remove(del.dataset.conndel); return; }
    const lab = e.target.closest && e.target.closest("[data-clab]");
    if (lab) { e.stopPropagation(); e.preventDefault(); edit(lab.dataset.clab); return; }
    const cc = e.target.closest && e.target.closest("[data-cc]");
    if (!cc) return;
    e.stopPropagation(); e.preventDefault();
    pull = { id: cc.dataset.cc, before: snap(), cur: toWorld(e.clientX, e.clientY), target: null }; renderLinks();
  }, true);
  addEventListener("pointermove", e => {
    if (!pull) return;
    pull.cur = toWorld(e.clientX, e.clientY);
    const t = dropAt(e.clientX, e.clientY, pull.id), id = t ? t.dataset.id : null;
    if (id !== pull.target) { outline(pull.el, false); pull.target = id; pull.el = t; outline(t, true); }
    renderLinks();
  });
  addEventListener("pointerup", () => {
    if (!pull) return; const p = pull; pull = null; outline(p.el, false);
    const id = p.target && add(board, p.id, p.target);
    if (id) { commit(p.before); sel = new Set([p.id]); render(); } else renderLinks();
  });
  function remove(id) {
    if (!table(board)[id]) return; const before = snap(); delete board.links[id]; prune(board); commit(before);
    toast(T("Arrow removed"), "info", { actions: [{ label: T("Undo"), fn: () => { if (past[past.length - 1] === before) undo(); } }] });
  }

  // ---- the words, the line and the colour of one arrow ----
  let ed = null;   // { id, el, before }
  function edit(id) {
    close(); const c = table(board)[id]; if (!c) return;
    const g = document.querySelector(`#links [data-clab="${id}"]`), r = g ? g.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 };
    const el = document.createElement("div"); el.className = "cned"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", T("Arrow"));
    const seg = (cls, val, opts) => `<hy-segmented class="${cls}" size="s" variant="well" value="${val}">`
      + opts.map(([v, t]) => `<button value="${v}">${esc(T(t))}</button>`).join("") + "</hy-segmented>";
    el.innerHTML = `<input class="cnin" maxlength="60" placeholder="${esc(T("Words on the arrow"))}" value="${esc(c.label || "")}">`
      + seg("cnst", c.style || "solid", [["solid", "line::Solid"], ["dashed", "line::Dashed"], ["dotted", "line::Dotted"]])
      + seg("cncol", c.color || "grey", [["grey", "line::Grey"], ["blue", "line::Blue"]]);
    document.body.appendChild(el);
    const x = Math.max(8, Math.min(r.left + r.width / 2 - el.offsetWidth / 2, innerWidth - el.offsetWidth - 8)), y = Math.max(8, Math.min(r.top + r.height + 10, innerHeight - el.offsetHeight - 8));
    Object.assign(el.style, { left: x + "px", top: y + "px" });
    ed = { id, el, before: snap() };
    const inp = el.querySelector(".cnin"); inp.focus(); inp.select();
    const set = (k, v, empty) => { const cc = table(board)[id]; if (!cc) return; if (!v || v === empty) delete cc[k]; else cc[k] = v; renderLinks(); };
    inp.addEventListener("input", () => set("label", inp.value.trim().slice(0, 60), ""));
    inp.addEventListener("keydown", e => { e.stopPropagation(); if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); close(); } });   // Esc applies, as everywhere on the board
    el.querySelector(".cnst").addEventListener("hy-change", e => set("style", e.detail.value, "solid"));
    el.querySelector(".cncol").addEventListener("hy-change", e => set("color", e.detail.value, "grey"));
    el.addEventListener("pointerdown", e => e.stopPropagation());
  }
  function close() {   // one undo step for the words, the line and the colour
    if (!ed) return; const { el, before } = ed; ed = null; el.remove();
    if (before !== snap()) commit(before); else renderLinks();
  }
  addEventListener("wheel", () => close(), { passive: true });

  // ---- Mermaid out: «Copy as › Mermaid» and ⌥⌘M (st3), the same text as hy.py mermaid ----
  function mermaid(b, ids) {
    const keep = ids && ids.length ? new Set(ids.flatMap(i => b.groups[i] ? [i, ...b.groups[i].members] : [i])) : null;
    const Ls = Object.values(table(b)).filter(c => !keep || (keep.has(c.from) && keep.has(c.to)));
    const words = i => { const g = b.groups[i], it = b.items[i] || {};
      const t = g ? g.title : it.type === "note" || it.type === "text" ? it.text : it.type === "timeline" ? it.label : it.path || it.src || it.scene || it.type;
      return ((t || "").trim().split("\n")[0].replace(/^#+\s*/, "").split("/").pop() || i).slice(0, 60); };
    const key = new Map(), used = new Set();
    for (const i of new Set(Ls.flatMap(c => [c.from, c.to]))) {
      let base = words(i).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24) || "n"; if (!/^[a-z]/.test(base)) base = "n" + base;
      let k = base, n = 2; while (used.has(k)) k = base + n++; used.add(k); key.set(i, k);
    }
    const q = s => '"' + s.replace(/"/g, "'") + '"', out = ["flowchart LR", ...[...key].map(([i, k]) => `  ${k}[${q(words(i))}]`)], st = [];
    Ls.forEach((c, n) => {
      const blue = c.color === "blue", s = c.style || "solid", arrow = s !== "solid" ? "-.->" : blue ? "==>" : "-->", a = key.get(c.from), z = key.get(c.to);
      out.push(c.label ? (arrow === "-->" ? `  ${a} -- ${q(c.label)} --> ${z}` : `  ${a} ${arrow}|${q(c.label)}| ${z}`) : `  ${a} ${arrow} ${z}`);
      const css = [...(blue && s !== "solid" ? ["stroke:#3b82f6"] : []), ...(s === "dotted" ? ["stroke-dasharray:2 6"] : [])]; if (css.length) st.push(`  linkStyle ${n} ${css.join(",")}`);
    });
    return [...out, ...st, ...[...key].map(([i, k]) => `  %% hyimg: ${k} = ${i}`)].join("\n") + "\n";
  }
  function copyMermaid(ids) {
    const t = mermaid(board, ids); if (!Object.keys(table(board)).length) { toast(T("No arrows on this page")); return; }
    copyText(t, T("Mermaid copied: {n} arrows", { n: (t.match(/-->|-\.->|==>/g) || []).length }));
  }
  if (window.hyLink && hyLink.items && hyLink.copy) {   // «Copy as ›»: its items and its fallback act are applink.js's
    const items = hyLink.items, copy = hyLink.copy;
    const touches = () => { const S = new Set([...sel].flatMap(i => board.groups[i] ? [i, ...board.groups[i].members] : [i]));
      return Object.values(table(board)).some(c => S.has(c.from) || S.has(c.to)); };   // only when the selection has arrows to copy
    hyLink.items = kind => items(kind) + (touches() ? hyMenuItem('data-act="mermaid"', "copy", T("Mermaid"), ["⌥", "⌘", "M"]) : "");
    hyLink.copy = (act, params) => act === "mermaid" ? copyMermaid([...sel]) : copy(act, params);
  }
  addEventListener("keydown", e => {
    if (!(e.altKey && (e.metaKey || e.ctrlKey) && e.code === "KeyM") || e.target.closest("input, textarea, [contenteditable]")) return;
    e.preventDefault(); copyMermaid([...sel]);
  });

  window.hyConn = { prune, add, svg, handle, mermaid, edit, close, curve };
})();
