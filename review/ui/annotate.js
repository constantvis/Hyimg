// Annotations on the board (owner 2026-10-07: «Добавь annotations на доске рядом с notes, чтобы я прямо не заходя в картинку мог по ней
// рисовать и добавлять комменты, как в Figma»). A drawing lies on top of the canvas, never in a picture's pixels: pen (smooth freehand),
// arrow, rectangle, ellipse and a short text label, in the note colours. It is anchored to the object under it by the notes' rule of
// overlap (ui/notelink.js caught: a picture, a video, a PDF, any plugin's card), its points kept as shares of that object's box, so it
// moves and scales with it; on empty canvas it keeps board units. Eraser, select and move, ⌫, ⌘Z (one step a stroke or a comment action,
// in turn with the board's own steps). «Show annotations» and a filter by author hide them; both are this viewer's (localStorage).
//
// The tool sits in the dock beside the note: «Annotate» (P); its tools take the dock while it is on (HY.dock), as a plugin's editor:
// Comment C (ui/comments.js), Pen P, Arrow A, Rectangle R, Ellipse O, Text T, Eraser E, Select V, the colours, the eye, the authors,
// the comments list, Done (Esc). ⇧C on the board starts a comment directly (C alone crops).
// Storage and history are the server's (review/comments.py): annotations/<page>__<id>.json, events of the page.
//
//   hyAnnot.tool(name) | .exit()          enter a tool, leave the mode
//   hyAnnot.step({ undo, redo })          one undo step of a module on top of the board (comments.js)
//   hyAnnot.anchorAt(rect | point)        the object a drawing or a pin belongs to: { anchor, rel(x, y) -> [u, v], abs([u, v]) -> {x, y} }
//   hyAnnot.visible(by)                   shown by the eye and the authors' filter
(() => {
  if (window.hyAnnot) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  if (!document.querySelector('link[href$="ui/annotate.css"]')) {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL("annotate.css", SRC).href; (document.head || document.documentElement).appendChild(l);
  }
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)));
  const $ = q => document.querySelector(q), NS = "http://www.w3.org/2000/svg";
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem("cv.ann." + k); localStorage.setItem("cv.ann." + k, v); } catch { return null; } };
  const COLOR = c => (window.HY_COLORS && window.HY_COLORS[c]) || "#ef6a6a";
  const COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "grey"];
  let hidden = []; try { hidden = JSON.parse(store("hide") || "[]"); } catch {}
  const A = { items: new Map(), page: null, tool: null, color: COLORS.includes(store("color")) ? store("color") : "red", show: store("show") !== "0",
    hide: new Set(Array.isArray(hidden) ? hidden : []), sel: new Set(), stacks: {}, tools: {}, live: null, ready: false };
  const TOOLS = [["comment", "comment", "Comment", "C"], ["pen", "marker", "Pen", "P"], ["arrow", "drawArrow", "Arrow", "A"], ["rect", "drawRect", "Rectangle", "R"],
    ["ellipse", "drawEllipse", "Ellipse", "O"], ["text", "drawText", "Text", "T"], ["eraser", "eraser", "Eraser", "E"], ["select", "select", "Select", "V"]];
  const KEY = Object.fromEntries(TOOLS.map(t => [t[3].toLowerCase(), t[0]]));
  const RU_KEY = { "з": "p", "ф": "a", "к": "r", "щ": "o", "е": "t", "у": "e", "м": "v", "с": "c" };
  const ok = () => typeof board !== "undefined" && typeof HY !== "undefined" && typeof BOARD !== "undefined";
  const z = () => (typeof cam !== "undefined" ? cam.z : 1);

  // ---- the server ----------------------------------------------------------------------------------------------------------------
  async function api(path, body) {
    const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : { cache: "no-store" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || String(r.status));
    return d;
  }
  const fail = ex => { if (typeof toast === "function") toast(T("Not saved: {why}", { why: ex.message || ex }), "error"); };
  async function load() {
    if (!ok()) return;
    const page = BOARD;
    try {
      const d = await api("/api/annotations?name=" + encodeURIComponent(page));
      if (page !== BOARD || A.live) return;
      A.items = new Map((d.items || []).map(a => [a.id, a])); A.page = page; draw();
    } catch {}
  }
  const uid = () => "a" + Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, "0")).join("").slice(0, 11);
  async function put(items, restore) {
    for (const a of items) A.items.set(a.id, a);
    draw();
    for (const a of items) {
      try { const d = await api("/api/annotations", { op: "put", name: a.page || BOARD, item: restore ? { ...a, restore: true } : a }); d.items.forEach(x => A.items.set(x.id, x)); }
      catch (ex) { fail(ex); }
    }
    draw();
  }
  async function remove(ids) {
    ids.forEach(id => { A.items.delete(id); A.sel.delete(id); }); draw();
    try { await api("/api/annotations", { op: "delete", name: BOARD, ids }); } catch (ex) { fail(ex); }
  }

  // ---- undo: one step a stroke or a comment action, in turn with the board's own (canvas.html past / future) ------------------
  const ST = () => A.stacks[BOARD] || (A.stacks[BOARD] = { done: [], undone: [] });
  function step(s) { const st = ST(); st.done.push({ ...s, pastLen: past.length }); st.undone = []; if (st.done.length > 200) st.done.shift(); draw(); }
  const mineNext = redo => { const st = ST(), s = redo ? st.undone[st.undone.length - 1] : st.done[st.done.length - 1];
    return !!s && (redo ? future.length <= s.futureLen : past.length <= s.pastLen); };
  async function undoMine() { const st = ST(), s = st.done.pop(); if (!s) return; s.futureLen = future.length; st.undone.push(s); try { await s.undo(); } catch (ex) { fail(ex); } }
  async function redoMine() { const st = ST(), s = st.undone.pop(); if (!s) return; s.pastLen = past.length; st.done.push(s); try { await s.redo(); } catch (ex) { fail(ex); } }
  const typing = () => { const a = document.activeElement;
    return !!a && (a.isContentEditable || a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && !/^(range|checkbox|radio|button)$/i.test(a.type))); };
  function undoKey(e) {
    if (!(e.metaKey || e.ctrlKey) || e.altKey || !["z", "я"].includes((e.key || "").toLowerCase()) || typing() || !ok() || PREV) return;
    if (!mineNext(e.shiftKey)) return;
    e.preventDefault(); e.stopImmediatePropagation(); e.shiftKey ? redoMine() : undoMine();
  }

  // ---- geometry -----------------------------------------------------------------------------------------------------------------
  const boxOf = an => { if (!an) return null; const it = board.items[an.obj]; if (it) return rectOf(an.obj); return an.r ? { x: an.r[0], y: an.r[1], w: an.r[2], h: an.r[3] } : null; };
  const kindOf = it => (window.hyNoteLink ? hyNoteLink.kind(it) : it.type || "picture");
  const fileOf = it => it.path || it.src || it.scene || it.doc || "";
  // the object a drawing (a board rect) or a pin (a point) belongs to: the topmost one holding its centre, else the one it overlaps most
  function objectAt(r) {
    const c = { x: r.x + (r.w || 0) / 2, y: r.y + (r.h || 0) / 2 };
    let hold = null, best = null, bs = 0;
    for (const id in board.items) {
      const it = board.items[id]; if (!(window.hyNoteLink ? hyNoteLink.caught(it) : it.path)) continue;
      const q = rectOf(id); if (!q || !(q.w > 0)) continue;
      if (c.x >= q.x && c.x <= q.x + q.w && c.y >= q.y && c.y <= q.y + q.h) hold = id;   // later in the order lies on top
      const ix = Math.max(0, Math.min(r.x + (r.w || 0), q.x + q.w) - Math.max(r.x, q.x)) * Math.max(0, Math.min(r.y + (r.h || 0), q.y + q.h) - Math.max(r.y, q.y));
      const s = ix / Math.max(1, (r.w || 1) * (r.h || 1)); if (s > bs) { bs = s; best = id; }
    }
    return hold || (bs > .5 ? best : null) || headingAt(c);
  }
  // a heading under it, when no picture or card is (2026-10-09, note nu6e6cs2: a table's title cells are headings, a mark on one moves with it)
  function headingAt(c) {
    let h = null;
    for (const id in board.items) {
      const it = board.items[id], q = it && it.type === "text" && rectOf(id);
      if (q && q.w > 0 && c.x >= q.x && c.x <= q.x + q.w && c.y >= q.y && c.y <= q.y + q.h) h = id;
    }
    return h;
  }
  function anchorAt(r) {
    const id = objectAt(r), q = id && rectOf(id);
    if (!id) return { anchor: null, rel: (x, y) => [x, y], abs: p => ({ x: p[0], y: p[1] }), scale: 1 };
    const it = board.items[id];
    return { anchor: { obj: id, kind: kindOf(it), file: fileOf(it), r: [q.x, q.y, q.w, q.h].map(v => Math.round(v * 10) / 10) },
      rel: (x, y) => [(x - q.x) / q.w, (y - q.y) / q.h], abs: p => ({ x: q.x + p[0] * q.w, y: q.y + p[1] * q.h }), scale: q.w };
  }
  // a drawing in board units: points, line width, type size
  function inBoard(a) {
    const q = boxOf(a.anchor);
    if (a.anchor && !q) return null;
    const f = q ? (p => ({ x: q.x + p[0] * q.w, y: q.y + p[1] * q.h })) : (p => ({ x: p[0], y: p[1] })), s = q ? q.w : 1;
    return { pts: a.pts.map(f), w: a.w * s, size: (a.size || 0) * s };
  }
  function fromBoard(kind, pts, wB, sizeB, keep) {
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y), r = { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
    const at = keep !== undefined ? keepAnchor(keep) : anchorAt(r), s = at.scale;
    const out = { kind, color: A.color, pts: pts.map(p => at.rel(p.x, p.y).map(v => Math.round(v * 1e5) / 1e5)), w: wB / s, anchor: at.anchor, page: BOARD };
    if (kind === "text") out.size = sizeB / s;
    return out;
  }
  function keepAnchor(an) {
    const q = boxOf(an);
    if (!an || !q) return { anchor: null, rel: (x, y) => [x, y], scale: 1 };
    return { anchor: { ...an, r: [q.x, q.y, q.w, q.h].map(v => Math.round(v * 10) / 10) }, rel: (x, y) => [(x - q.x) / q.w, (y - q.y) / q.h], scale: q.w };
  }
  const segDist = (p, a, b) => { const dx = b.x - a.x, dy = b.y - a.y, l = dx * dx + dy * dy; let t = l ? ((p.x - a.x) * dx + (p.y - a.y) * dy) / l : 0;
    t = Math.max(0, Math.min(1, t)); return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy); };
  function outline(a, g) {   // the shape as a polyline in board units (hit tests, the selection box)
    const [p, q] = g.pts;
    if (a.kind === "rect") return [p, { x: q.x, y: p.y }, q, { x: p.x, y: q.y }, p];
    if (a.kind === "ellipse") { const cx = (p.x + q.x) / 2, cy = (p.y + q.y) / 2, rx = Math.abs(q.x - p.x) / 2, ry = Math.abs(q.y - p.y) / 2;
      return Array.from({ length: 37 }, (_, i) => ({ x: cx + rx * Math.cos(i * Math.PI / 18), y: cy + ry * Math.sin(i * Math.PI / 18) })); }
    if (a.kind === "text") { const w = g.size * .56 * (a.text || "").length, h = g.size * 1.25;
      return [{ x: p.x, y: p.y - h }, { x: p.x + w, y: p.y - h }, { x: p.x + w, y: p.y + h * .25 }, { x: p.x, y: p.y + h * .25 }, { x: p.x, y: p.y - h }]; }
    return g.pts;
  }
  function hit(pt, tol) {
    const ids = [...A.items.keys()].reverse();
    for (const id of ids) {
      const a = A.items.get(id); if (!visible(a.by)) continue;
      const g = inBoard(a); if (!g) continue;
      const o = outline(a, g), t = tol + g.w / 2;
      if (o.length === 1 ? Math.hypot(pt.x - o[0].x, pt.y - o[0].y) <= t : o.some((v, i) => i && segDist(pt, o[i - 1], v) <= t)) return id;
      if (a.kind === "text") { const xs = o.map(v => v.x), ys = o.map(v => v.y);
        if (pt.x >= Math.min(...xs) && pt.x <= Math.max(...xs) && pt.y >= Math.min(...ys) && pt.y <= Math.max(...ys)) return id; }
    }
    return null;
  }

  // ---- drawing them ------------------------------------------------------------------------------------------------------------
  const who = by => (by && by.person ? by.person : "") + "|" + ((window.HY_AGENTS ? HY_AGENTS.kind(by && by.via) : "") || "app");
  const visible = by => A.show && !A.hide.has(who(by));
  const f1 = v => Math.round(v * 10) / 10;
  function smooth(pts) {   // a pen line through the middles of its segments (quadratic curves), as freehand tools draw
    if (pts.length < 3) return `M${pts.map(p => `${f1(p.x)} ${f1(p.y)}`).join(" L")}${pts.length === 1 ? ` l.01 0` : ""}`;
    let d = `M${f1(pts[0].x)} ${f1(pts[0].y)}`;
    for (let i = 1; i < pts.length - 1; i++) { const m = { x: (pts[i].x + pts[i + 1].x) / 2, y: (pts[i].y + pts[i + 1].y) / 2 }; d += ` Q${f1(pts[i].x)} ${f1(pts[i].y)} ${f1(m.x)} ${f1(m.y)}`; }
    const l = pts[pts.length - 1]; return d + ` L${f1(l.x)} ${f1(l.y)}`;
  }
  // hy-allow-begin: icon-inline the drawings people make on the board and the box around the selected ones, not icons
  function shape(a, g) {
    const c = COLOR(a.color), w = Math.max(.5, g.w), [p, q] = g.pts, st = `fill="none" stroke="${c}" stroke-width="${f1(w)}" stroke-linecap="round" stroke-linejoin="round"`;
    if (a.kind === "pen") return `<path d="${smooth(g.pts)}" ${st}/>`;
    if (a.kind === "arrow") {
      const ang = Math.atan2(q.y - p.y, q.x - p.x), l = Math.max(w * 4.5, 10), h = k => `${f1(q.x - l * Math.cos(ang + k))} ${f1(q.y - l * Math.sin(ang + k))}`;
      return `<path d="M${f1(p.x)} ${f1(p.y)} L${f1(q.x)} ${f1(q.y)} M${h(.5)} L${f1(q.x)} ${f1(q.y)} L${h(-.5)}" ${st}/>`;
    }
    if (a.kind === "rect") return `<rect x="${f1(Math.min(p.x, q.x))}" y="${f1(Math.min(p.y, q.y))}" width="${f1(Math.abs(q.x - p.x))}" height="${f1(Math.abs(q.y - p.y))}" rx="${f1(w)}" ${st}/>`;
    if (a.kind === "ellipse") return `<ellipse cx="${f1((p.x + q.x) / 2)}" cy="${f1((p.y + q.y) / 2)}" rx="${f1(Math.abs(q.x - p.x) / 2)}" ry="${f1(Math.abs(q.y - p.y) / 2)}" ${st}/>`;
    if (a.kind === "text") return `<text x="${f1(p.x)}" y="${f1(p.y)}" font-size="${f1(g.size)}" fill="${c}" class="ann-t">${esc(a.text)}</text>`;
    return "";
  }
  function layer() {
    let s = document.getElementById("annsvg");
    if (!s && $("#world")) { s = document.createElementNS(NS, "svg"); s.id = "annsvg"; s.setAttribute("aria-hidden", "true"); $("#world").appendChild(s); }
    return s;
  }
  function draw() {
    if (!ok()) return;
    if (A.page !== BOARD) { A.items = new Map(); A.sel.clear(); A.page = BOARD; load(); }
    const s = layer(); if (!s) return;
    s.classList.toggle("off", !A.show);
    const want = new Map();
    const all = A.live ? [...A.items.values(), A.live] : [...A.items.values()];
    for (const a of all) {
      if (!visible(a.by || A.me())) continue;
      const g = inBoard(a); if (!g) continue;
      want.set(a.id, shape(a, g) + (A.sel.has(a.id) ? selBox(a, g) : ""));
    }
    for (const el of [...s.children]) if (!want.has(el.dataset.a)) el.remove();
    for (const [id, h] of want) {
      let el = s.querySelector(`:scope > g[data-a="${id}"]`);
      if (!el) { el = document.createElementNS(NS, "g"); el.dataset.a = id; s.appendChild(el); }
      if (el._h !== h) { el.innerHTML = h; el._h = h; }
      // its object ("" the board; none while being drawn): a Studio lays the drawings of other things under its card (ui/editlift.js)
      const a = A.items.get(id), o = a ? (a.anchor && a.anchor.obj) || "" : null;
      if (o == null) delete el.dataset.o; else if (el.dataset.o !== o) el.dataset.o = o;
    }
    if (window.hyComments) hyComments.draw();
    const st = ST(), bu = $("#bundo"), br = $("#bredo");   // the dock's undo and redo stay on while a step of ours waits (render greys them by the board's)
    if (bu && st.done.length) bu.disabled = false;
    if (br && st.undone.length) br.disabled = false;
  }
  function selBox(a, g) {
    const o = outline(a, g), xs = o.map(v => v.x), ys = o.map(v => v.y), pad = 6 / z() + g.w / 2;
    return `<rect class="ann-sel" x="${f1(Math.min(...xs) - pad)}" y="${f1(Math.min(...ys) - pad)}" width="${f1(Math.max(...xs) - Math.min(...xs) + pad * 2)}"`
      + ` height="${f1(Math.max(...ys) - Math.min(...ys) + pad * 2)}" style="stroke-width:${f1(1.5 / z())}px;stroke-dasharray:${f1(4 / z())} ${f1(3 / z())}"/>`;
  }
  // hy-allow-end

  // ---- the tools ---------------------------------------------------------------------------------------------------------------
  const onBoard = e => (e.target === stage || (e.target.closest && e.target.closest("#world, .bgl, #marq, #gsticky"))) && !(e.target.closest && e.target.closest(".cmpin"));
  let D = null;   // the gesture in progress
  function down(e) {
    if (!A.tool || e.button !== 0 || (typeof space !== "undefined" && space) || !ok() || !onBoard(e)) return;
    if (!bar || !bar.isConnected) { gone(); return; }
    // on the window, first of all: an editor that ends on a press elsewhere (an HTML frame's live view) never sees a stroke
    e.preventDefault(); e.stopPropagation();
    if (PREV) { toast(T("This is a version preview. To change it, press “Restore this version”")); return; }
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    const p = toWorld(e.clientX, e.clientY), t = A.tool;
    if (A.tools[t]) { D = { ext: A.tools[t], p }; A.tools[t].down(e, p); }
    else if (t === "text") textAt(p, e);
    else if (t === "eraser") { D = { erase: new Set() }; erase(p); }
    else if (t === "select") {
      const id = hit(p, 5 / z());
      if (!id) { A.sel.clear(); draw(); return; }
      if (e.shiftKey) A.sel.has(id) ? A.sel.delete(id) : A.sel.add(id); else if (!A.sel.has(id)) A.sel = new Set([id]);
      D = { move: [...A.sel].map(i => [i, JSON.parse(JSON.stringify(A.items.get(i)))]), p, moved: false }; draw();
    } else {
      A.live = { id: uid(), kind: t, color: A.color, pts: [[p.x, p.y], [p.x, p.y]], w: 3 / z(), anchor: null, page: BOARD };
      if (t === "pen") A.live.pts = [[p.x, p.y]];
      D = { draw: t, p0: p, raw: [p] }; draw();
    }
    try { stage.setPointerCapture(e.pointerId); } catch {}
  }
  function move(e) {
    if (!D) return;
    const p = toWorld(e.clientX, e.clientY);
    if (D.ext) { D.ext.move && D.ext.move(e, p); return; }
    if (D.erase) { erase(p); return; }
    if (D.move) {
      const dx = p.x - D.p.x, dy = p.y - D.p.y; if (!D.moved && Math.hypot(dx, dy) * z() < 3) return; D.moved = true;
      for (const [id, a0] of D.move) { const g = inBoard(a0); if (!g) continue;
        const k = fromBoard(a0.kind, g.pts.map(q => ({ x: q.x + dx, y: q.y + dy })), g.w, g.size, a0.anchor);
        A.items.set(id, { ...a0, pts: k.pts, anchor: k.anchor }); }
      draw(); return;
    }
    if (D.draw === "pen") { const last = D.raw[D.raw.length - 1]; if (Math.hypot(p.x - last.x, p.y - last.y) * z() < 2) return; D.raw.push(p); A.live.pts = D.raw.map(q => [q.x, q.y]); }
    else { let q = p; if (e.shiftKey) q = constrain(D.draw, D.p0, p); A.live.pts = [[D.p0.x, D.p0.y], [q.x, q.y]]; }
    draw();
  }
  function constrain(kind, a, p) {
    const dx = p.x - a.x, dy = p.y - a.y;
    if (kind === "arrow") { const ang = Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) * Math.PI / 4, l = Math.hypot(dx, dy); return { x: a.x + l * Math.cos(ang), y: a.y + l * Math.sin(ang) }; }
    const m = Math.max(Math.abs(dx), Math.abs(dy)); return { x: a.x + Math.sign(dx || 1) * m, y: a.y + Math.sign(dy || 1) * m };
  }
  function up(e) {
    if (!D) return;
    const d = D; D = null;
    if (d.ext) { d.ext.up && d.ext.up(e, toWorld(e.clientX, e.clientY)); return; }
    if (d.erase) { const ids = [...d.erase]; d.erase.clear(); s0(ids); if (ids.length) erased(ids); return; }
    if (d.move) {
      if (!d.moved) return;
      const after = d.move.map(([id]) => A.items.get(id)), before = d.move.map(([, a]) => a);
      put(after); step({ undo: () => put(before), redo: () => put(after) }); return;
    }
    const live = A.live; A.live = null;
    let pts = d.raw.length > 1 && d.draw === "pen" ? simplify(d.raw, .6 / z()) : live.pts.map(q => ({ x: q[0], y: q[1] }));
    if (d.draw !== "pen" && Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) * z() < 4) { draw(); return; }   // a click, not a shape
    const a = { ...fromBoard(d.draw, pts, 3 / z(), 0), id: live.id, by: A.me() };
    put([a]); step({ undo: () => remove([a.id]), redo: () => put([a], true) });
  }
  function s0(ids) { ids.forEach(id => { const g = document.querySelector(`#annsvg g[data-a="${id}"]`); if (g) g.classList.remove("erasing"); }); }
  function erase(p) {
    const id = hit(p, 6 / z()); if (!id || D.erase.has(id)) return;
    D.erase.add(id); const g = document.querySelector(`#annsvg g[data-a="${id}"]`); if (g) g.classList.add("erasing");
  }
  function erased(ids) {
    const gone = ids.map(id => A.items.get(id)).filter(Boolean);
    remove(ids); step({ undo: () => put(gone, true), redo: () => remove(gone.map(a => a.id)) });
  }
  function simplify(pts, tol) {   // Ramer-Douglas-Peucker: the line keeps its shape with far fewer points
    if (pts.length < 3) return pts;
    let far = 0, at = 0; for (let i = 1; i < pts.length - 1; i++) { const d = segDist(pts[i], pts[0], pts[pts.length - 1]); if (d > far) { far = d; at = i; } }
    if (far <= tol) return [pts[0], pts[pts.length - 1]];
    return [...simplify(pts.slice(0, at + 1), tol).slice(0, -1), ...simplify(pts.slice(at), tol)];
  }
  function textAt(p, e) {
    const inp = document.createElement("input"), r = stage.getBoundingClientRect();
    inp.className = "ann-input"; inp.maxLength = 200; inp.placeholder = T("Text"); inp.style.left = e.clientX - r.left + "px"; inp.style.top = e.clientY - r.top - 12 + "px";
    inp.style.setProperty("--c", COLOR(A.color)); stage.appendChild(inp); inp.focus(); requestAnimationFrame(() => inp.focus());
    let done = false;
    const end = keep => {
      if (done) return; done = true; const t = inp.value.trim(); inp.remove();
      if (!keep || !t) return;
      const a = { ...fromBoard("text", [{ x: p.x, y: p.y + 6 / z() }], 3 / z(), 16 / z()), text: t, id: uid(), by: A.me() };
      put([a]); step({ undo: () => remove([a.id]), redo: () => put([a], true) });
    };
    inp.addEventListener("keydown", k => { k.stopPropagation(); if (k.key === "Enter" || k.key === "Escape") { k.preventDefault(); end(k.key === "Enter" || !!inp.value.trim()); } });
    inp.addEventListener("blur", () => end(true));
  }

  // ---- the mode: the dock's tools -------------------------------------------------------------------------------------------------
  let bar = null;
  function toolbar() {
    if (bar) return bar;
    bar = document.createElement("div"); bar.className = "ann-bar";
    const sw = COLORS.map(c => `<hy-swatch size="s" value="${c}" color="${COLOR(c)}" label="${esc(T(c))}"${c === A.color ? " selected" : ""}></hy-swatch>`).join("");
    // the comment first, the drawing tools after a line (owner 2026-10-07: «такой простой вариант», the shapes are the extra)
    const btn = ([k, ic, label, key]) => `<button class="ic" data-tool="${k}" title="${esc(T(label))} · ${key}" aria-label="${esc(T(label))}">${hyIcon(ic, 18, 1.85)}</button>`;
    bar.innerHTML = btn(TOOLS[0]) + `<span class="sep"></span>` + TOOLS.slice(1).map(btn).join("")
      + `<span class="sep"></span><hy-swatches class="ann-sw" value="${A.color}" label="${esc(T("Colour"))}">${sw}</hy-swatches><span class="sep"></span>`
      + `<button class="ic" data-ann="eye" title="${esc(T("Show annotations"))}" aria-label="${esc(T("Show annotations"))}"></button>`
      + `<button class="ic" data-ann="who" title="${esc(T("Whose annotations"))}" aria-label="${esc(T("Whose annotations"))}">${hyIcon("filter", 17, 1.85)}</button>`
      + `<button class="ic ann-list" data-ann="list" title="${esc(T("Comments on this page"))}" aria-label="${esc(T("Comments on this page"))}">`
      + `${hyIcon("list", 17, 1.85)}<hy-badge class="ann-n" count="0"></hy-badge></button>`
      + `<button class="wide" data-ann="done" title="Esc">${esc(T("Done"))}</button>`;
    bar.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.tool) { tool(b.dataset.tool); return; }
      const k = b.dataset.ann;
      if (k === "eye") setShow(!A.show); else if (k === "who") whoMenu(b); else if (k === "list") window.hyComments && hyComments.list(); else if (k === "done") exit();
    });
    bar.addEventListener("hy-change", e => { if (e.target.closest(".ann-sw")) { A.color = e.detail.value; store("color", A.color); recolor(); } });
    return bar;
  }
  function recolor() {   // the colour picked applies to the selected drawings too, one step
    const before = [...A.sel].map(id => A.items.get(id)).filter(Boolean); if (!before.length) return;
    const after = before.map(a => ({ ...a, color: A.color })); put(after); step({ undo: () => put(before), redo: () => put(after) });
  }
  function paintBar() {
    if (!bar) return;
    bar.querySelectorAll("[data-tool]").forEach(b => { b.classList.toggle("on", b.dataset.tool === A.tool); b.setAttribute("aria-pressed", String(b.dataset.tool === A.tool)); });
    const eye = bar.querySelector('[data-ann="eye"]'); eye.innerHTML = hyIcon(A.show ? "eye" : "eyeoff", 17, 1.85); eye.classList.toggle("off", !A.show);
    bar.querySelector('[data-ann="who"]').classList.toggle("on", A.hide.size > 0);
    const n = window.hyComments ? hyComments.openCount() : 0; bar.querySelector(".ann-n").setAttribute("count", String(n));
  }
  // over an HTML page in an editor (Dev mode, an HTML frame's live view, owner 2026-10-07: «поверх картинки статичной, либо еще как») the
  // tools borrow the dock and give it back on Done; other editors (3D, Image) keep their keys and the dock
  const hostOk = () => document.body.classList.contains("dvedit") || !!document.querySelector(".plg-live[data-type=htmlframe]");
  function tool(name) {
    if (!ok() || PREV) return;
    const busy = $("#dock").classList.contains("plg-mode") && !(bar && bar.isConnected);
    if (!A.tool && busy && !hostOk()) return;   // another editor holds the dock
    if (typeof sel !== "undefined" && sel.size) { sel.clear(); render(); }
    if (!A.tool) A.host = busy ? $("#dock .plgdock") : null;
    A.tool = name; A.sel.clear();
    HY.dock(toolbar()); stage.classList.add("annot"); stage.dataset.annTool = name; $("#bann") && $("#bann").classList.add("on");
    if (A.kh) A.kh.hide(); A.kh = window.hyHint ? hyHint("ann:" + name, bar) : null;   // the tool's keys in the Hint bar at the top (ui/boardhints.js)
    if (!A.show) setShow(true);
    paintBar(); draw();
  }
  function exit() {
    if (!A.tool) return;
    A.tool = null; A.sel.clear(); D = null; A.live = null; if (A.kh) { A.kh.hide(); A.kh = null; }
    if (bar && bar.isConnected) HY.dock(A.host || null);   // the editor's own dock back (Dev mode), else the board's
    A.host = null; stage.classList.remove("annot"); delete stage.dataset.annTool; $("#bann") && $("#bann").classList.remove("on");
    if (window.hyComments) hyComments.cancelDraft();
    draw();
  }
  // the dock went to someone else (the editor under us closed): the tools stop without touching it
  function gone() { if (!A.tool) return; A.host = null; if (bar) bar.remove(); exit(); }
  function setShow(on) { A.show = on; store("show", on ? "1" : "0"); paintBar(); draw(); }
  // the authors of what is on this page (drawings and threads), a click hides or shows each
  function whoMenu(btn) {
    let m = document.getElementById("annwho"); if (m) { m.remove(); return; }
    const by = new Map();
    for (const a of A.items.values()) if (a.by) by.set(who(a.by), a.by);
    if (window.hyComments) hyComments.authors().forEach(b => by.set(who(b), b));
    m = document.createElement("div"); m.id = "annwho"; m.setAttribute("role", "menu");
    m.innerHTML = `<div class="nh0">${esc(T("Whose annotations"))}</div>` + ([...by].map(([k, b]) => `<button role="menuitemcheckbox" aria-checked="${!A.hide.has(k)}" data-who="${esc(k)}">`
      + `${window.hyAvatarOf ? hyAvatarOf(b, 20) : ""}<span>${esc(window.hyWhoText ? hyWhoText({ by: b }) : k)}</span>${hyIcon("check", 14, 2.2, "ck")}</button>`).join("")
      || `<div class="none">${esc(T("Nothing on this page yet"))}</div>`);
    stage.appendChild(m);
    const r = btn.getBoundingClientRect(), s = stage.getBoundingClientRect();
    m.style.left = Math.max(8, r.left - s.left - 100) + "px"; m.style.bottom = s.bottom - r.top + 10 + "px";
    m.addEventListener("click", e => {
      const b = e.target.closest("[data-who]"); if (!b) return;
      const k = b.dataset.who; A.hide.has(k) ? A.hide.delete(k) : A.hide.add(k); store("hide", JSON.stringify([...A.hide]));
      b.setAttribute("aria-checked", String(!A.hide.has(k))); paintBar(); draw();
    });
    setTimeout(() => addEventListener("pointerdown", function off(e) { if (!m.contains(e.target) && e.target !== btn) { m.remove(); removeEventListener("pointerdown", off, true); } }, true));
  }
  function keys(e) {
    if (typing() || !ok()) return;
    const k = (e.key || "").toLowerCase(), mod = e.metaKey || e.ctrlKey, code = (e.code || "").replace(/^Key/, "").toLowerCase();
    if (!A.tool) {   // on the board: P draws, ⇧C comments (C alone crops)
      if (mod || e.altKey || PREV || ($("#dock").classList.contains("plg-mode") && !hostOk())) return;
      if (document.body.classList.contains("dvedit") && (code === "c" || k === "c" || k === "с")) return;   // Dev mode's own C: a comment on an element
      if (!e.shiftKey && (code === "p" || k === "p" || k === "з")) { e.preventDefault(); e.stopImmediatePropagation(); tool("pen"); }
      else if (e.shiftKey && (code === "c" || k === "c" || k === "с")) { e.preventDefault(); e.stopImmediatePropagation(); tool("comment"); }
      return;
    }
    if (mod) return;   // ⌘Z and the rest: undoKey and the board
    e.stopImmediatePropagation(); if (A.kh && A.kh.key) A.kh.key(e);   // the key hint's own listener comes after this one: told here
    if (e.key === "Escape") { e.preventDefault(); if (window.hyComments && hyComments.escape()) return; if (A.sel.size) { A.sel.clear(); draw(); return; } exit(); return; }
    if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); if (A.sel.size) erased([...A.sel]); return; }
    if (e.key === " ") return;   // the board's hand
    const t = KEY[code] || KEY[k] || KEY[RU_KEY[k]];
    if (t && !e.shiftKey) { e.preventDefault(); tool(t); }
  }

  // ---- wiring ----------------------------------------------------------------------------------------------------------------------
  function init() {
    if (!ok() || A.ready || !$("#btl")) return void setTimeout(init, 100);
    A.ready = true;
    const b = document.createElement("button");
    b.id = "bann"; b.className = "ic"; b.title = T("Comment and draw · ⇧C"); b.setAttribute("aria-label", T("Annotate")); b.innerHTML = hyIcon("comment", 18, 1.85);
    b.onclick = () => (A.tool ? exit() : tool("comment")); $("#btl").after(b);
    addEventListener("pointerdown", down, true);
    new MutationObserver(() => { if (A.tool && bar && !bar.isConnected) gone(); }).observe($("#dock"), { childList: true });
    addEventListener("pointermove", move, true); addEventListener("pointerup", up, true); addEventListener("pointercancel", up, true);
    addEventListener("keydown", undoKey, true); addEventListener("keydown", keys, true);
    ["#bundo", "#bredo"].forEach((q, i) => { const el = $(q); if (el) el.addEventListener("click", e => {
      if (!mineNext(i === 1)) return; e.stopImmediatePropagation(); i ? redoMine() : undoMine(); }, true); });
    // the board's render and camera: anchored drawings follow their objects, pins and the open thread follow the camera
    const r0 = window.render; window.render = function (...a) { const out = r0.apply(this, a); try { draw(); } catch (ex) { console.error("annotate", ex); } return out; };
    const c0 = window.renderCam; window.renderCam = function (...a) { const out = c0.apply(this, a); try { window.hyComments && hyComments.follow(); } catch {} return out; };
    const keysPanel = $("#keys");   // the shortcuts panel: one line for the two keys
    if (keysPanel) keysPanel.insertAdjacentHTML("beforeend", `<div><span class="k"><kbd>⇧</kbd><kbd>C</kbd> <kbd>P</kbd></span> ${esc(T("comment, an area by a drag; draw"))}</div>`);
    HY.ctx(ids => ids.length ? [] : [{ icon: A.show ? "eyeoff" : "eye", label: A.show ? T("Hide annotations") : T("Show annotations"), fn: () => setShow(!A.show) }]);
    load(); setInterval(() => { if (!D && !document.hidden) load(); }, 8000);
  }
  A.me = () => { const m = window.hyPeople && hyPeople.me(); return m ? { person: m.id, via: "app" } : { via: "app" }; };
  window.hyAnnot = { get state() { return A; }, tool, exit, step, anchorAt, keepAnchor, visible, who, api, draw, paintBar, fail, boxOf, register: (k, def) => { A.tools[k] = def; },
    get active() { return A.tool; }, undoMine, redoMine };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
