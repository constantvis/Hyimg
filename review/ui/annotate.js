// The drawing tools of Annotations, waiting for later (owner 2026-10-09: «Режим аннотации очень крутой, но я бы его спрятал. Нам не нужны
// вообще эти рисовалки. Эту функцию я бы вынес в "доработать потом", чтобы она не загружала нашу систему»; docs/LATER.md). The board
// never loads this file unless localStorage cv.annDraw is "1" (ui/anncore.js, after a reload); there is no switch in the interface.
//
// What it was (owner 2026-10-07: «Добавь annotations на доске рядом с notes, чтобы я прямо не заходя в картинку мог по ней рисовать»): a
// drawing lies on top of the canvas, never in a picture's pixels: pen (smooth freehand), arrow, rectangle, ellipse and a short text label,
// in the note colours, anchored to the object under it (ui/anncore.js anchorAt), so it moves and scales with it. Eraser, select and move,
// ⌫, ⌘Z. With it on, a tool takes the dock (HY.dock), as a plugin's editor: Annotation C, Pen P, Arrow A, Rectangle R, Ellipse O, Text T,
// Eraser E, Select V, the colours, the eye, the authors' filter, the page's annotations, Done (Esc). P on the board takes the pen.
// Storage and history are the server's (review/comments.py): annotations/<page>__<id>.json, events of the page.
(() => {
  const AN = window.hyAnnot; if (!AN || AN.drawing) return;
  const A = AN.state;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)));
  const $ = q => document.querySelector(q);
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem("cv.ann." + k); localStorage.setItem("cv.ann." + k, v); } catch { return null; } };
  const COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "grey"];
  A.color = COLORS.includes(store("color")) ? store("color") : "red";
  const TOOLS = [["comment", "comment", "Annotation", "C"], ["pen", "marker", "Pen", "P"], ["arrow", "drawArrow", "Arrow", "A"], ["rect", "drawRect", "Rectangle", "R"],
    ["ellipse", "drawEllipse", "Ellipse", "O"], ["text", "drawText", "Text", "T"], ["eraser", "eraser", "Eraser", "E"], ["select", "select", "Select", "V"]];
  const KEY = Object.fromEntries(TOOLS.map(t => [t[3].toLowerCase(), t[0]]));
  const RU_KEY = { "з": "p", "ф": "a", "к": "r", "щ": "o", "е": "t", "у": "e", "м": "v", "с": "c" };
  const z = () => AN.z();
  const uid = () => "a" + Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, "0")).join("").slice(0, 11);

  // ---- geometry -----------------------------------------------------------------------------------------------------------------
  function fromBoard(kind, pts, wB, sizeB, keep) {
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y), r = { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
    const at = keep !== undefined ? AN.keepAnchor(keep) : AN.anchorAt(r), s = at.scale;
    const out = { kind, color: A.color, pts: pts.map(p => at.rel(p.x, p.y).map(v => Math.round(v * 1e5) / 1e5)), w: wB / s, anchor: at.anchor, page: BOARD };
    if (kind === "text") out.size = sizeB / s;
    return out;
  }
  const segDist = (p, a, b) => { const dx = b.x - a.x, dy = b.y - a.y, l = dx * dx + dy * dy; let t = l ? ((p.x - a.x) * dx + (p.y - a.y) * dy) / l : 0;
    t = Math.max(0, Math.min(1, t)); return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy); };
  function hit(pt, tol) {
    for (const id of [...A.items.keys()].reverse()) {
      const a = A.items.get(id); if (!AN.visible(a.by)) continue;
      const g = AN.inBoard(a); if (!g) continue;
      const o = AN.outline(a, g), t = tol + g.w / 2;
      if (o.length === 1 ? Math.hypot(pt.x - o[0].x, pt.y - o[0].y) <= t : o.some((v, i) => i && segDist(pt, o[i - 1], v) <= t)) return id;
      if (a.kind === "text") { const xs = o.map(v => v.x), ys = o.map(v => v.y);
        if (pt.x >= Math.min(...xs) && pt.x <= Math.max(...xs) && pt.y >= Math.min(...ys) && pt.y <= Math.max(...ys)) return id; }
    }
    return null;
  }
  function constrain(kind, a, p) {
    const dx = p.x - a.x, dy = p.y - a.y;
    if (kind === "arrow") { const ang = Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) * Math.PI / 4, l = Math.hypot(dx, dy); return { x: a.x + l * Math.cos(ang), y: a.y + l * Math.sin(ang) }; }
    const m = Math.max(Math.abs(dx), Math.abs(dy)); return { x: a.x + Math.sign(dx || 1) * m, y: a.y + Math.sign(dy || 1) * m };
  }
  function simplify(pts, tol) {   // Ramer-Douglas-Peucker: the line keeps its shape with far fewer points
    if (pts.length < 3) return pts;
    let far = 0, at = 0; for (let i = 1; i < pts.length - 1; i++) { const d = segDist(pts[i], pts[0], pts[pts.length - 1]); if (d > far) { far = d; at = i; } }
    if (far <= tol) return [pts[0], pts[pts.length - 1]];
    return [...simplify(pts.slice(0, at + 1), tol).slice(0, -1), ...simplify(pts.slice(at), tol)];
  }

  // ---- the tools (hyAnnot.register: the press reaches them from ui/anncore.js) -----------------------------------------------------
  let D = null;
  const alive = () => { if (bar && bar.isConnected) return true; gone(); return false; };
  const shapeTool = kind => ({
    down(e, p) {
      if (!alive()) return;
      A.live = { id: uid(), kind, color: A.color, pts: kind === "pen" ? [[p.x, p.y]] : [[p.x, p.y], [p.x, p.y]], w: 3 / z(), anchor: null, page: BOARD };
      D = { p0: p, raw: [p] }; AN.draw();
    },
    move(e, p) {
      if (!D || !A.live) return;
      if (kind === "pen") { const last = D.raw[D.raw.length - 1]; if (Math.hypot(p.x - last.x, p.y - last.y) * z() < 2) return; D.raw.push(p); A.live.pts = D.raw.map(q => [q.x, q.y]); }
      else { const q = e.shiftKey ? constrain(kind, D.p0, p) : p; A.live.pts = [[D.p0.x, D.p0.y], [q.x, q.y]]; }
      AN.draw();
    },
    up() {
      const d = D, live = A.live; D = null; A.live = null; if (!d || !live) return;
      const pts = d.raw.length > 1 && kind === "pen" ? simplify(d.raw, .6 / z()) : live.pts.map(q => ({ x: q[0], y: q[1] }));
      if (kind !== "pen" && Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) * z() < 4) { AN.draw(); return; }   // a click, not a shape
      const a = { ...fromBoard(kind, pts, 3 / z(), 0), id: live.id, by: A.me() };
      AN.put([a]); AN.step({ undo: () => AN.remove([a.id]), redo: () => AN.put([a], true) });
    },
  });
  ["pen", "arrow", "rect", "ellipse"].forEach(k => AN.register(k, shapeTool(k)));
  AN.register("text", { down(e, p) { if (alive()) textAt(p, e); } });
  AN.register("eraser", {
    down(e, p) { if (!alive()) return; D = { erase: new Set() }; erase(p); },
    move(e, p) { if (D && D.erase) erase(p); },
    up() { const d = D; D = null; if (!d || !d.erase) return; const ids = [...d.erase]; ids.forEach(lit(false)); if (ids.length) erased(ids); },
  });
  AN.register("select", {
    down(e, p) {
      if (!alive()) return;
      const id = hit(p, 5 / z());
      if (!id) { A.sel.clear(); AN.draw(); return; }
      if (e.shiftKey) A.sel.has(id) ? A.sel.delete(id) : A.sel.add(id); else if (!A.sel.has(id)) A.sel = new Set([id]);
      D = { move: [...A.sel].map(i => [i, JSON.parse(JSON.stringify(A.items.get(i)))]), p, moved: false }; AN.draw();
    },
    move(e, p) {
      if (!D || !D.move) return;
      const dx = p.x - D.p.x, dy = p.y - D.p.y; if (!D.moved && Math.hypot(dx, dy) * z() < 3) return; D.moved = true;
      for (const [id, a0] of D.move) { const g = AN.inBoard(a0); if (!g) continue;
        const k = fromBoard(a0.kind, g.pts.map(q => ({ x: q.x + dx, y: q.y + dy })), g.w, g.size, a0.anchor);
        A.items.set(id, { ...a0, pts: k.pts, anchor: k.anchor }); }
      AN.draw();
    },
    up() {
      const d = D; D = null; if (!d || !d.move || !d.moved) return;
      const after = d.move.map(([id]) => A.items.get(id)), before = d.move.map(([, a]) => a);
      AN.put(after); AN.step({ undo: () => AN.put(before), redo: () => AN.put(after) });
    },
  });
  const lit = on => id => { const g = document.querySelector(`#annsvg g[data-a="${id}"]`); if (g) g.classList.toggle("erasing", on); };
  function erase(p) { const id = hit(p, 6 / z()); if (!id || D.erase.has(id)) return; D.erase.add(id); lit(true)(id); }
  function erased(ids) {
    const gone_ = ids.map(id => A.items.get(id)).filter(Boolean);
    AN.remove(ids); AN.step({ undo: () => AN.put(gone_, true), redo: () => AN.remove(gone_.map(a => a.id)) });
  }
  function textAt(p, e) {
    const inp = document.createElement("input"), r = stage.getBoundingClientRect();
    inp.className = "ann-input"; inp.maxLength = 200; inp.placeholder = T("Text"); inp.style.left = e.clientX - r.left + "px"; inp.style.top = e.clientY - r.top - 12 + "px";
    inp.style.setProperty("--c", AN.COLOR(A.color)); stage.appendChild(inp); inp.focus(); requestAnimationFrame(() => inp.focus());
    let done = false;
    const end = keep => {
      if (done) return; done = true; const t = inp.value.trim(); inp.remove();
      if (!keep || !t) return;
      const a = { ...fromBoard("text", [{ x: p.x, y: p.y + 6 / z() }], 3 / z(), 16 / z()), text: t, id: uid(), by: A.me() };
      AN.put([a]); AN.step({ undo: () => AN.remove([a.id]), redo: () => AN.put([a], true) });
    };
    inp.addEventListener("keydown", k => { k.stopPropagation(); if (k.key === "Enter" || k.key === "Escape") { k.preventDefault(); end(k.key === "Enter" || !!inp.value.trim()); } });
    inp.addEventListener("blur", () => end(true));
  }

  // ---- the dock while a tool is in hand -------------------------------------------------------------------------------------------
  let bar = null;
  function toolbar() {
    if (bar) return bar;
    bar = document.createElement("div"); bar.className = "ann-bar";
    const sw = COLORS.map(c => `<hy-swatch size="s" value="${c}" color="${AN.COLOR(c)}" label="${esc(T(c))}"${c === A.color ? " selected" : ""}></hy-swatch>`).join("");
    const btn = ([k, ic, label, key]) => `<button class="ic" data-tool="${k}" title="${esc(T(label))} · ${key}" aria-label="${esc(T(label))}">${hyIcon(ic, 18, 1.85)}</button>`;
    bar.innerHTML = btn(TOOLS[0]) + `<span class="sep"></span>` + TOOLS.slice(1).map(btn).join("")
      + `<span class="sep"></span><hy-swatches class="ann-sw" value="${A.color}" label="${esc(T("Colour"))}">${sw}</hy-swatches><span class="sep"></span>`
      + `<button class="ic" data-ann="eye" title="${esc(T("Show annotations"))}" aria-label="${esc(T("Show annotations"))}"></button>`
      + `<button class="ic" data-ann="who" title="${esc(T("Whose annotations"))}" aria-label="${esc(T("Whose annotations"))}">${hyIcon("filter", 17, 1.85)}</button>`
      + `<button class="ic ann-list" data-ann="list" title="${esc(T("Annotations on this page"))}" aria-label="${esc(T("Annotations on this page"))}">`
      + `${hyIcon("list", 17, 1.85)}<hy-badge class="ann-n" count="0"></hy-badge></button>`
      + `<button class="wide" data-ann="done" title="Esc">${esc(T("Done"))}</button>`;
    bar.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.tool) { AN.tool(b.dataset.tool); return; }
      const k = b.dataset.ann;
      if (k === "eye") AN.setShow(!A.show); else if (k === "who") whoMenu(b); else if (k === "list") window.hyComments && hyComments.list(); else if (k === "done") AN.exit();
    });
    bar.addEventListener("hy-change", e => { if (e.target.closest(".ann-sw")) { A.color = e.detail.value; store("color", A.color); recolor(); } });
    return bar;
  }
  function recolor() {   // the colour picked applies to the selected drawings too, one step
    const before = [...A.sel].map(id => A.items.get(id)).filter(Boolean); if (!before.length) return;
    const after = before.map(a => ({ ...a, color: A.color })); AN.put(after); AN.step({ undo: () => AN.put(before), redo: () => AN.put(after) });
  }
  function paintBar() {
    if (!bar) return;
    bar.querySelectorAll("[data-tool]").forEach(b => { b.classList.toggle("on", b.dataset.tool === A.tool); b.setAttribute("aria-pressed", String(b.dataset.tool === A.tool)); });
    const eye = bar.querySelector('[data-ann="eye"]'), ic = hyIcon(A.show ? "eye" : "eyeoff", 17, 1.85);
    if (eye._ic !== ic) { eye.innerHTML = ic; eye._ic = ic; } eye.classList.toggle("off", !A.show);
    bar.querySelector('[data-ann="who"]').classList.toggle("on", A.hide.size > 0);
    const n = window.hyComments ? hyComments.openCount() : 0; bar.querySelector(".ann-n").setAttribute("count", String(n));
  }
  // the dock went to someone else (the editor under us closed): the tools stop without touching it
  function gone() { if (!A.tool) return; A.host = null; if (bar) bar.remove(); AN.exit(); }
  // the authors of what is on this page (drawings and threads), a click hides or shows each
  function whoMenu(btn) {
    let m = document.getElementById("annwho"); if (m) { m.remove(); return; }
    const by = new Map();
    for (const a of A.items.values()) if (a.by) by.set(AN.who(a.by), a.by);
    if (window.hyComments) hyComments.authors().forEach(b => by.set(AN.who(b), b));
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
      b.setAttribute("aria-checked", String(!A.hide.has(k))); AN.draw();
    });
    setTimeout(() => addEventListener("pointerdown", function off(e) { if (!m.contains(e.target) && e.target !== btn) { m.remove(); removeEventListener("pointerdown", off, true); } }, true));
  }

  // ---- hooked into ui/anncore.js ----------------------------------------------------------------------------------------------------
  A.ext = {
    docked: () => !!(bar && bar.isConnected),
    bar: () => (bar && bar.isConnected ? bar : null),
    // over an HTML page in an editor (Dev Studio, an HTML frame's live view) the tools borrow the dock and give it back on Done
    onTool(name, first, busy) { if (first) A.host = busy ? $("#dock .plgdock") : null; if (!(bar && bar.isConnected)) HY.dock(toolbar()); D = null; paintBar(); },
    onExit() { D = null; if (bar && bar.isConnected) HY.dock(A.host || null); A.host = null; },
    paint: paintBar,
    key(e, k, code) {
      if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); if (A.sel.size) erased([...A.sel]); return true; }
      const t = KEY[code] || KEY[k] || KEY[RU_KEY[k]];
      if (t && !e.shiftKey) { e.preventDefault(); AN.tool(t); return true; }
      return false;
    },
    boardKey(e, k, code) { if (!e.shiftKey && (code === "p" || k === "p" || k === "з")) { e.preventDefault(); e.stopImmediatePropagation(); AN.tool("pen"); } },
  };
  new MutationObserver(() => { if (A.tool && bar && !bar.isConnected) gone(); }).observe($("#dock"), { childList: true });
  const keysPanel = $("#keys");
  if (keysPanel) keysPanel.insertAdjacentHTML("beforeend", `<div><span class="k"><kbd>P</kbd></span> ${esc(T("draw"))}</div>`);
  const b = $("#bann"); if (b) b.title = T("Annotation and drawing · C, P");
  AN.draw();
})();
