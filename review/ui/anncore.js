// Annotations on the board, the part every board loads (owner 2026-10-09: «Режим аннотации очень крутой, но я бы его спрятал. Нам не
// нужны вообще эти рисовалки ... сделай вместо комментариев Annotations: комментарии будут на букву, а не на комбинацию Shift C»). What the
// interface calls an Annotation is a pin with a thread (ui/comments.js; in the code, the server and hy.py still «comment»). C on the board
// starts one, as in Figma: the pointer becomes the pin, a click drops it, a drag draws an area; the dock stays as it is, Esc leaves.
// The drawing tools (pen, arrow, shapes, text, eraser, select) wait for later (docs/LATER.md): ui/annotate.js, loaded only when the flag
// cv.annDraw is "1" in localStorage, no switch in the interface. Drawings already on a board still show here, read only.
//
// This file: the server, undo in turn with the board, the object a pin or a drawing belongs to, the drawings' layer, the Annotation tool
// (C, the dock's button), the eye, and what the drawing tools hook into (hyAnnot.ext).
//   hyAnnot.tool(name) | .exit()          enter a tool («comment»; the drawing tools when ui/annotate.js is on), leave it
//   hyAnnot.step({ undo, redo })          one undo step of a module on top of the board (comments.js, annotate.js)
//   hyAnnot.anchorAt(rect | point)        the object a drawing or a pin belongs to: { anchor, rel(x, y) -> [u, v], abs([u, v]) -> {x, y} }
//   hyAnnot.visible(by)                   shown by the eye (and the authors' filter, which lives with the drawing tools)
//   hyAnnot.drawing                       true when the drawing tools are loaded
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
  const flag = () => { try { return localStorage.getItem("cv.annDraw") === "1"; } catch { return false; } };
  const COLOR = c => (window.HY_COLORS && window.HY_COLORS[c]) || "#ef6a6a";
  let hidden = []; try { hidden = JSON.parse(store("hide") || "[]"); } catch {}
  const A = { items: new Map(), page: null, tool: null, color: "red", show: store("show") !== "0", hide: new Set(Array.isArray(hidden) ? hidden : []), sel: new Set(),
    stacks: {}, tools: {}, live: null, ready: false, ext: null };
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
  async function load() {   // the page's drawings: shown read only here, the drawing tools change them
    if (!ok()) return;
    const page = BOARD;
    try {
      const d = await api("/api/annotations?name=" + encodeURIComponent(page));
      if (page !== BOARD || A.live) return;
      A.items = new Map((d.items || []).map(a => [a.id, a])); A.page = page; draw();
    } catch {}
  }
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

  // ---- undo: one step a stroke or an annotation's action, in turn with the board's own (canvas.html past / future) ---------------
  // A step remembers where it was made: on the board, or in the Studio holding the dock. ⌘Z in a Studio never undoes the board's
  // annotation, nor ⌘Z under a viewer (the video player, a PDF's page) (P4 B-07)
  const ST = () => A.stacks[BOARD] || (A.stacks[BOARD] = { done: [], undone: [] });
  const place = () => ($("#dock").classList.contains("plg-mode") && !docked() ? "studio:" + ((typeof MODES !== "undefined" && MODES && MODES.open) || "") : "board");
  const viewer = () => typeof VBIG !== "undefined" && !!VBIG;
  function step(s) { const st = ST(); st.done.push({ ...s, pastLen: past.length, at: place() }); st.undone = []; if (st.done.length > 200) st.done.shift(); draw(); }
  const mineNext = redo => { const st = ST(), s = redo ? st.undone[st.undone.length - 1] : st.done[st.done.length - 1];
    return !!s && !viewer() && s.at === place() && (redo ? future.length <= s.futureLen : past.length <= s.pastLen); };
  // a step moves to the other stack once the server has taken it (P4 B-51): one the server refused stays where it was; a second ⌘Z
  // while the first is on its way waits for it
  async function turn(from, to, dir, mark) {
    const st = ST(), s = st[from][st[from].length - 1]; if (!s || s.busy) return; s.busy = true;
    try { await s[dir](); st[from].pop(); s[mark] = mark === "futureLen" ? future.length : past.length; st[to].push(s); } catch (ex) { fail(ex); } finally { s.busy = false; }
  }
  const undoMine = () => turn("done", "undone", "undo", "futureLen"), redoMine = () => turn("undone", "done", "redo", "pastLen");
  const typing = e => window.hyTyping(e);   // a field typed in takes every key, ⌘Z too (ui/typing.js)
  function undoKey(e) {   // in a Studio ⌘Z is the Studio's own step, never an annotation before it (P4 S-13)
    if (!(e.metaKey || e.ctrlKey) || e.altKey || !["z", "я"].includes((e.key || "").toLowerCase()) || typing(e) || !ok() || PREV) return;
    if (typeof MODES !== "undefined" && MODES && MODES.open !== "board") return;   // asked now, not the attribute a frame later
    if (!mineNext(e.shiftKey)) return;
    e.preventDefault(); e.stopImmediatePropagation(); e.shiftKey ? redoMine() : undoMine();
  }

  // ---- geometry -----------------------------------------------------------------------------------------------------------------
  // the box of what a pin or a drawing belongs to; its object gone (deleted, cut, moved to another page): none, the pin hides until ⌘Z
  // brings the object back (P4 B-32: the pin stayed at the stored place); an anchor without an object keeps its stored box
  const boxOf = an => { if (!an) return null; if (board.items[an.obj]) return rectOf(an.obj); return !an.obj && an.r ? { x: an.r[0], y: an.r[1], w: an.r[2], h: an.r[3] } : null; };
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
  function keepAnchor(an) {
    const q = boxOf(an);
    if (!an || !q) return { anchor: null, rel: (x, y) => [x, y], scale: 1 };
    return { anchor: { ...an, r: [q.x, q.y, q.w, q.h].map(v => Math.round(v * 10) / 10) }, rel: (x, y) => [(x - q.x) / q.w, (y - q.y) / q.h], scale: q.w };
  }
  // a drawing in board units: points, line width, type size
  function inBoard(a) {
    const q = boxOf(a.anchor);
    if (a.anchor && !q) return null;
    const f = q ? (p => ({ x: q.x + p[0] * q.w, y: q.y + p[1] * q.h })) : (p => ({ x: p[0], y: p[1] })), s = q ? q.w : 1;
    return { pts: a.pts.map(f), w: a.w * s, size: (a.size || 0) * s };
  }
  function outline(a, g) {   // the shape as a polyline in board units (hit tests, the selection box)
    const [p, q] = g.pts;
    if (a.kind === "rect") return [p, { x: q.x, y: p.y }, q, { x: p.x, y: q.y }, p];
    if (a.kind === "ellipse") { const cx = (p.x + q.x) / 2, cy = (p.y + q.y) / 2, rx = Math.abs(q.x - p.x) / 2, ry = Math.abs(q.y - p.y) / 2;
      return Array.from({ length: 37 }, (_, i) => ({ x: cx + rx * Math.cos(i * Math.PI / 18), y: cy + ry * Math.sin(i * Math.PI / 18) })); }
    if (a.kind === "text") { const w = g.size * .56 * (a.text || "").length, h = g.size * 1.25;
      return [{ x: p.x, y: p.y - h }, { x: p.x + w, y: p.y - h }, { x: p.x + w, y: p.y + h * .25 }, { x: p.x, y: p.y + h * .25 }, { x: p.x, y: p.y - h }]; }
    return g.pts;
  }

  // ---- drawing them ------------------------------------------------------------------------------------------------------------
  const who = by => (by && by.person ? by.person : "") + "|" + ((window.HY_AGENTS ? HY_AGENTS.kind(by && by.via) : "") || "app");
  // the authors' filter is the drawing tools' (its menu is theirs): without them nothing stays hidden by it
  const visible = by => A.show && !(A.ext && A.hide.has(who(by)));
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
  function selBox(a, g) {
    const o = outline(a, g), xs = o.map(v => v.x), ys = o.map(v => v.y), pad = 6 / z() + g.w / 2;
    return `<rect class="ann-sel" x="${f1(Math.min(...xs) - pad)}" y="${f1(Math.min(...ys) - pad)}" width="${f1(Math.max(...xs) - Math.min(...xs) + pad * 2)}"`
      + ` height="${f1(Math.max(...ys) - Math.min(...ys) + pad * 2)}" style="stroke-width:${f1(1.5 / z())}px;stroke-dasharray:${f1(4 / z())} ${f1(3 / z())}"/>`;
  }
  // hy-allow-end
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
    if (A.ext && A.ext.paint) A.ext.paint();
    const st = ST(), bu = $("#bundo"), br = $("#bredo");   // the dock's undo and redo stay on while a step of ours waits (render greys them by the board's)
    if (bu && st.done.length) bu.disabled = false;
    if (br && st.undone.length) br.disabled = false;
  }

  // ---- the tool in hand: the press goes to it, on the window before anything (hyAnnot.register: comments.js, annotate.js) ---------
  const onBoard = e => (e.target === stage || (e.target.closest && e.target.closest("#world, .bgl, #marq, #gsticky"))) && !(e.target.closest && e.target.closest(".cmpin"));
  let D = null;   // the gesture in progress: { t: the tool's handlers }
  function down(e) {
    if (!A.tool || e.button !== 0 || (typeof space !== "undefined" && space) || !ok() || !onBoard(e)) return;
    const t = A.tools[A.tool]; if (!t) return;
    // on the window, first of all: an editor that ends on a press elsewhere (an HTML frame's live view) never sees the press
    e.preventDefault(); e.stopPropagation();
    if (PREV) { toast(T("This is a version preview. To change it, press “Restore this version”")); return; }
    if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    const p = toWorld(e.clientX, e.clientY); D = { t }; t.down(e, p);
    try { stage.setPointerCapture(e.pointerId); } catch {}
  }
  function move(e) { if (D && D.t.move) D.t.move(e, toWorld(e.clientX, e.clientY)); }
  function up(e) { if (!D) return; const d = D; D = null; if (d.t.up) d.t.up(e, toWorld(e.clientX, e.clientY)); }

  // ---- the mode ------------------------------------------------------------------------------------------------------------------
  // over an HTML page in an editor (Dev Studio, an HTML frame's live view, owner 2026-10-07: «поверх картинки статичной, либо еще как»)
  // the tool works too; other editors (3D, Image) keep their keys and the dock
  const hostOk = () => document.body.classList.contains("dvedit") || !!document.querySelector(".plg-live[data-type=htmlframe]");
  const docked = () => !!(A.ext && A.ext.docked && A.ext.docked());
  function tool(name) {
    if (!ok() || PREV || !A.tools[name]) return;
    const busy = $("#dock").classList.contains("plg-mode") && !docked();
    if (!A.tool && busy && !hostOk()) return;   // another editor holds the dock
    // the selection waits under the tool and comes back when it ends (owner decision 2026-10-10, P4 B-61); one tool at a time (B-30)
    if (!A.tool && typeof cropState !== "undefined" && cropState && typeof applyCrop === "function") applyCrop();
    if (!A.tool && typeof sel !== "undefined") { A.kept = new Set(sel); if (sel.size) { sel.clear(); render(); } }
    const first = !A.tool;
    A.tool = name; A.sel.clear();
    if (A.ext && A.ext.onTool) A.ext.onTool(name, first, busy);   // the drawing tools take the dock
    stage.classList.add("annot"); stage.dataset.annTool = name; $("#bann") && $("#bann").classList.add("on");
    if (A.kh) A.kh.hide();   // the tool's keys in the Hint bar at the top (ui/boardhints.js)
    A.kh = window.hyHint ? hyHint("ann:" + name, (A.ext && A.ext.bar && A.ext.bar()) || $("#bann") || stage) : null;
    if (!A.show) setShow(true);
    draw();
  }
  function exit() {
    if (!A.tool) return;
    A.tool = null; A.sel.clear(); D = null; A.live = null; if (A.kh) { A.kh.hide(); A.kh = null; }
    if (A.ext && A.ext.onExit) A.ext.onExit();
    stage.classList.remove("annot"); delete stage.dataset.annTool; $("#bann") && $("#bann").classList.remove("on");
    if (window.hyComments) hyComments.cancelDraft();
    const k = A.kept; A.kept = null;   // the selection from before the tool, what of it is still there
    if (k && typeof sel !== "undefined" && !sel.size) { sel = new Set([...k].filter(id => board.items[id] || board.groups[id])); if (sel.size && typeof render === "function") render(); }
    draw();
  }
  function setShow(on) { A.show = on; store("show", on ? "1" : "0"); draw(); }
  const isC = (e, k, code) => code === "c" || k === "c" || k === "с";
  function keys(e) {
    if (typing(e) || !ok()) return;
    const k = (e.key || "").toLowerCase(), mod = e.metaKey || e.ctrlKey, code = (e.code || "").replace(/^Key/, "").toLowerCase();
    if (!A.tool) {   // on the board: C starts an annotation (⇧C crops, canvas.html)
      if (mod || e.altKey || PREV || ($("#dock").classList.contains("plg-mode") && !hostOk())) return;
      if (document.body.classList.contains("dvedit") && isC(e, k, code)) return;   // Dev Studio's own C: an annotation on an element
      if (!e.shiftKey && isC(e, k, code)) { e.preventDefault(); e.stopImmediatePropagation(); tool("comment"); return; }
      if (A.ext && A.ext.boardKey) A.ext.boardKey(e, k, code);   // P: the drawing tools
      return;
    }
    // ⌘Z and the rest: undoKey and the board; Space, ! and \ are the board's with the tool on (P4 B-09, B-31): it pans, shows all, the library
    if (mod || e.key === " " || e.key === "!" || e.key === "\\" || ["Shift", "Alt", "Meta", "Control", "CapsLock"].includes(e.key)) return;
    if (A.kh && A.kh.key) A.kh.key(e);   // the key hint's own listener comes after this one: told here
    if (e.key === "Escape") {
      e.stopImmediatePropagation(); e.preventDefault(); if (window.hyComments && hyComments.escape()) return; if (A.sel.size) { A.sel.clear(); draw(); return; } exit(); return;
    }
    if (A.ext && A.ext.key && A.ext.key(e, k, code)) { e.stopImmediatePropagation(); return; }   // the drawing tools' letters, ⌫ for their selection
    // V back to the board's pointer, as in Figma; C again turns the tool off (owner decision 2026-10-10, B-61); any other key of the board
    // ends the tool and does its own work (B-31: N, F, L, ⌫, the arrows did nothing)
    if (!e.shiftKey && (code === "v" || k === "v" || k === "м" || isC(e, k, code))) { e.stopImmediatePropagation(); e.preventDefault(); exit(); return; }
    exit();
  }

  // ---- wiring ----------------------------------------------------------------------------------------------------------------------
  function init() {
    if (!ok() || A.ready || !$("#dtools")) return void setTimeout(init, 100);
    A.ready = true;
    const b = document.createElement("button");
    b.id = "bann"; b.className = "ic"; b.title = T("Annotation · C"); b.setAttribute("aria-label", T("Annotation")); b.innerHTML = hyIcon("comment", 18, 1.85);
    b.onclick = () => (A.tool ? exit() : tool("comment")); $("#dtools").appendChild(b);   // the dock's tools (ui/boarddock.js)
    addEventListener("pointerdown", down, true);
    addEventListener("pointermove", move, true); addEventListener("pointerup", up, true); addEventListener("pointercancel", up, true);
    addEventListener("keydown", undoKey, true); addEventListener("keydown", keys, true);
    ["#bundo", "#bredo"].forEach((q, i) => { const el = $(q); if (el) el.addEventListener("click", e => {
      if (!mineNext(i === 1)) return; e.stopImmediatePropagation(); i ? redoMine() : undoMine(); }, true); });
    // the board's render and camera: anchored drawings follow their objects, pins and the open thread follow the camera
    const r0 = window.render; window.render = function (...a) { const out = r0.apply(this, a); try { draw(); } catch (ex) { console.error("annotate", ex); } return out; };
    const c0 = window.renderCam; window.renderCam = function (...a) { const out = c0.apply(this, a); try { window.hyComments && hyComments.follow(); } catch {} return out; };
    const keysPanel = $("#keys");   // the shortcuts panel
    if (keysPanel) keysPanel.insertAdjacentHTML("beforeend", `<div><span class="k"><kbd>C</kbd></span> ${esc(T("annotation, an area by a drag; C again ends it"))}</div>`);
    // the empty board's right click: the eye, the page's annotations
    HY.ctx(ids => ids.length ? [] : [{ icon: A.show ? "eyeoff" : "eye", label: A.show ? T("Hide annotations") : T("Show annotations"), fn: () => setShow(!A.show) },
      { icon: "list", label: T("Annotations on this page"), fn: () => window.hyComments && hyComments.list() }]);
    load(); setInterval(() => { if (!D && !document.hidden) load(); }, 8000);
    if (flag()) { const s = document.createElement("script"); s.src = new URL("annotate.js", SRC).href; document.head.appendChild(s); }   // later (docs/LATER.md)
  }
  A.me = () => { const m = window.hyPeople && hyPeople.me(); return m ? { person: m.id, via: "app" } : { via: "app" }; };
  window.hyAnnot = { get state() { return A; }, tool, exit, step, anchorAt, keepAnchor, visible, who, api, draw, fail, boxOf, inBoard, outline, put, remove, setShow, z,
    paintBar: () => { if (A.ext && A.ext.paint) A.ext.paint(); }, register: (k, def) => { A.tools[k] = def; }, get active() { return A.tool; }, get drawing() { return !!A.ext; },
    undoMine, redoMine, COLOR };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
