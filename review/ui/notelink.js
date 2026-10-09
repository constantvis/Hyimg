// What a sticky note is linked to, for every kind of thing on the board (owner 2026-10-07: «Почему я не могу HTML указать: ноут
// добавить, и чтобы он так же, как на картинку, ссылался? Что 3D, что картинка, неважно что, это объект»). Until then canvas.html
// tested pictures only: an arrow could not end on an HTML card, and a note pointing at one fell back to its group.
// The rule is review/notelinks.py's, the server's and hy.py's: overlap, the zone holding a thing's centre, an arrow (at a group: its
// members), and a note with none of those inside a group frame speaks for the whole group. A thing is a picture, a video, a PDF or
// any plugin's card (an HTML frame or page, a 3D scene, an image frame, a card of a plugin not named here); a heading and a timeline
// take only an arrow; a note is never a thing of another note.
// A reply (owner 2026-10-08: «как ответ на заметку ... просто протягиваю стрелку, как к любой картинке, так к объекту заметки»): an
// arrow from a note to another note, kept in the same "to", answers it; one per note, chains allowed, a circle refused. The reply is
// about what the notes up its chain are about ("reply"); its own links work as for any note and it never speaks for its group.
(() => {
  const ARROW_ONLY = new Set(["text", "timeline"]);
  const KIND = { htmlframe: "html", html: "html", model3d: "3d", imgframe: "frame", text: "heading", timeline: "timeline" };
  // a count of each kind, in this order: «1 HTML page, 2 frames»
  const WORD = { picture: "{n} frames", video: "{n} videos", pdf: "{n} PDFs", html: "{n} HTML pages", "3d": "{n} 3D scenes",
    frame: "{n} image frames", heading: "{n} headings", timeline: "{n} timelines", card: "{n} cards" };
  const target = it => !!it && it.type !== "note" && !!(it.type || it.path);   // an arrow may end on it
  const caught = it => target(it) && !ARROW_ONLY.has(it.type);   // overlap, a zone and a group's note catch it
  const libKind = p => (typeof byPath !== "undefined" && byPath.get(p) || {}).kind;   // the library knows a video or a PDF by its file
  function kind(it) {
    if (it.type) return KIND[it.type] || "card";
    const k = libKind(it.path), p = (it.path || "").toLowerCase();
    return k === "video" || /\.(mp4|mov|m4v|webm)$/.test(p) ? "video" : k === "pdf" || p.endsWith(".pdf") ? "pdf" : "picture";
  }
  const hit = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  const holds = (r, p) => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;

  // things by cells of the board, for the passes that ask about every note (owner 2026-10-02: 520 notes and 3600 frames each redraw
  // took 340 ms); built once per pass. Returns r => the things whose box may touch r
  function index(board, rectOf, keep = caught) {
    const C = 2048, cells = new Map(), key = (i, j) => i * 1e6 + j;
    for (const id in board.items) {
      if (!keep(board.items[id])) continue; const q = rectOf(id), e = { id, q };
      for (let i = Math.floor(q.x / C); i <= Math.floor((q.x + q.w) / C); i++) for (let j = Math.floor(q.y / C); j <= Math.floor((q.y + q.h) / C); j++) {
        const k = key(i, j); let c = cells.get(k); if (!c) cells.set(k, c = []); c.push(e);
      }
    }
    return r => {
      const seen = new Set(), out = [];
      for (let i = Math.floor(r.x / C); i <= Math.floor((r.x + r.w) / C); i++) for (let j = Math.floor(r.y / C); j <= Math.floor((r.y + r.h) / C); j++)
        for (const e of cells.get(key(i, j)) || []) if (!seen.has(e)) { seen.add(e); out.push(e); }
      return out;
    };
  }

  // Map thing id -> Set(overlap | zone | arrow | group); .group is the group id when the note speaks for a whole group.
  // near: index() of this pass, else every thing is looked at; rectOf, reachRect, noteGroup: canvas.html's
  function links(board, nid, near, rectOf, reachRect, noteGroup, up) {   // up: a parent's own links, for a reply
    const n = board.items[nid], out = new Map(), add = (id, v) => { if (!out.has(id)) out.set(id, new Set()); out.get(id).add(v); };
    const r = rectOf(nid), z = reachRect(n), members = g => g.members.filter(m => caught(board.items[m]));
    const box = z ? { x: Math.min(r.x, z.x), y: Math.min(r.y, z.y), w: Math.max(r.x + r.w, z.x + z.w) - Math.min(r.x, z.x), h: Math.max(r.y + r.h, z.y + z.h) - Math.min(r.y, z.y) } : r;
    const pool = near ? near(box) : Object.keys(board.items).filter(id => caught(board.items[id])).map(id => ({ id, q: rectOf(id) }));
    for (const { id, q } of pool) { if (hit(r, q)) add(id, "overlap"); if (z && holds(z, { x: q.x + q.w / 2, y: q.y + q.h / 2 })) add(id, "zone"); }
    (n.to || []).forEach(t => { if (t !== nid && target(board.items[t])) add(t, "arrow"); else if (board.groups[t]) members(board.groups[t]).forEach(m => add(m, "arrow")); });
    // only a note with no zone and no arrows speaks for its group: a zone, even an empty one, means "these things" (2026-10-01)
    if (!out.size && !n.reach && !(n.to || []).length) { const gid = noteGroup(nid); if (gid) { members(board.groups[gid]).forEach(m => add(m, "group")); if (out.size) out.group = gid; } }
    // a reply: the things of the notes up its chain (their own links, not what they inherit), as review/notelinks.py
    if (!up) for (let p = replyOf(board, nid), seen = new Set([nid]); p && !seen.has(p); seen.add(p), p = replyOf(board, p))
      if ((board.items[p].text || "").trim()) links(board, p, near, rectOf, reachRect, noteGroup, true).forEach((v, id) => add(id, "reply"));
    return out;
  }

  // ---- replies (owner 2026-10-08) ----
  const isNote = it => !!it && it.type === "note";
  const replyOf = (board, nid) => ((board.items[nid] || {}).to || []).find(t => t !== nid && isNote(board.items[t])) || null;
  const byPos = board => (a, b) => (board.items[a].y - board.items[b].y) || (board.items[a].x - board.items[b].x);
  const replies = (board, nid) => Object.keys(board.items).filter(k => isNote(board.items[k]) && replyOf(board, k) === nid).sort(byPos(board));
  function circle(board, nid, t) { for (let p = t, seen = new Set(); p && !seen.has(p); seen.add(p), p = replyOf(board, p)) if (p === nid) return true; return false; }
  const words = (t, n = 6) => { const w = ((t || "").trim().split("\n")[0].replace(/^#+\s*/, "")).split(/\s+/).filter(Boolean); return w.slice(0, n).join(" ") + (w.length > n ? "…" : ""); };
  // the arrow let go on a note: nid answers t (its earlier reply arrow goes). {ok, msg}: the toast in either case
  function reply(board, nid, t) {
    const n = board.items[nid];
    if (circle(board, nid, t)) return { ok: false, msg: T("Can't reply in a circle: that note already answers this one") };
    if (replyOf(board, nid) === t) return { ok: false, msg: "" };
    n.to = (n.to || []).filter(x => !isNote(board.items[x])).concat(t);
    return { ok: true, msg: T("Reply to “{text}”", { text: words(board.items[t].text) || T("Sticky note") }) };
  }
  // a new note made with notes selected (N, the dock's button) answers the last of them; place: right of it, its top in line, moved
  // along until it covers nothing (further right, then a row lower), when no selected picture or card has placed it already
  function placeReply(board, id, parent, rectOf, place) {
    const n = board.items[id]; n.to = [...(n.to || []), parent]; if (!place) return;
    const r = rectOf(parent), gap = Math.round(n.w * .25), h = n.w;
    const others = Object.keys(board.items).filter(k => k !== id).map(k => rectOf(k)).filter(Boolean);
    const free = (x, y) => !others.some(q => x < q.x + q.w + gap / 2 && x + n.w + gap / 2 > q.x && y < q.y + q.h && y + h > q.y);
    for (let i = 0; i < 48; i++) {
      const x = r.x + r.w + gap + (i % 8) * (n.w + gap), y = r.y + Math.floor(i / 8) * (h + gap);
      if (free(x, y)) { n.x = Math.round(x); n.y = Math.round(y); return; }
    }
    n.x = Math.round(r.x + r.w + gap); n.y = Math.round(r.y);
  }
  // every note of the thread a note is in: up to the first note, then down every reply
  function chain(board, nid) {
    let root = nid; for (let p = replyOf(board, nid), seen = new Set([nid]); p && !seen.has(p); seen.add(p), p = replyOf(board, p)) root = p;
    const out = new Set(), walk = k => { if (out.has(k)) return; out.add(k); replies(board, k).forEach(walk); }; walk(root); return out;
  }
  // hy-allow-begin: icon-inline the board's own drawing: the dashed outline of the selected note's thread
  function chainSvg(board, nid, rectOf, col) {   // board units only: its line, dashes and corners on screen in CSS (canvas.html .lkc)
    const C = chain(board, nid); if (C.size < 2) return "";
    return [...C].filter(k => k !== nid).map(k => {
      const r = rectOf(k), m = 8; if (!r) return "";
      return `<rect class="lkc" x="${r.x - m}" y="${r.y - m}" width="${r.w + 2 * m}" height="${r.h + 2 * m}" fill="none" stroke="${col}"/>`;
    }).join("");
  }
  // hy-allow-end
  // the Info of a note: «Reply to: …» (a click goes to that note) and «Replies · N», each with its author
  function replyInfo(root, nid) {
    const up = replyOf(board, nid), down = replies(board, nid).filter(k => (board.items[k].text || "").trim());
    const sec = (title, ids, line) => {
      const s = document.createElement("section"), h = document.createElement("div"); s.className = "isec"; h.className = "sh"; h.textContent = title; if (title) s.appendChild(h);
      ids.forEach(id => {
        const n = board.items[id], b = document.createElement("button"); b.className = "inote"; b.style.setProperty("--nc", noteCol(n)[0]); b.title = T("Go to the note");
        b.innerHTML = `<div class="t">${line(n)}</div>` + (n.by && window.hyWho ? `<div class="muted">${hyWho({ by: n.by }, "who")}</div>` : "");
        b.onclick = () => { goTo(id); render(); }; s.appendChild(b);
      });
      root.appendChild(s);
    };
    if (up) sec("", [up], n => escH(T("Reply to: “{text}”", { text: words(n.text) || T("Sticky note") })));
    if (down.length) sec(`${T("Replies")} · ${down.length}`, down, n => mdHtml(n.text));
  }

  // «1 HTML page, 2 frames»
  function what(board, ids) {
    const n = {}; ids.forEach(id => { const k = kind(board.items[id]); n[k] = (n[k] || 0) + 1; });
    return Object.keys(WORD).filter(k => n[k]).map(k => T(WORD[k], { n: n[k] })).join(", ");
  }
  // the Info line of a note: pictures alone as before («goes into these frames' json»), with a card «the AI reads it with them»
  function meta(board, ids, groupName) {
    const pics = ids.every(id => !board.items[id].type), frames = T("{n} frames", { n: ids.length }), w = what(board, ids);
    if (groupName != null) return pics ? T("belongs to the whole group “{name}”: {frames} · goes into these frames' json", { name: groupName, frames })
      : T("belongs to the whole group “{name}”: {what} · the AI reads it with them", { name: groupName, what: w });
    if (!ids.length) return null;
    return pics ? T("linked: {frames} · goes into these frames' json", { frames }) : T("linked: {what} · the AI reads it with them", { what: w });
  }
  // a thing's name in the note's list: a picture by its library name, a card by its plugin's name and its file, a heading by its text
  function label(board, id) {
    const it = board.items[id], file = it.src || it.scene || it.doc || "";
    if (!it.type) { const m = typeof byPath !== "undefined" && byPath.get(it.path) || {}; return m.name || it.path; }
    if (it.type === "text") return (it.text || "").split("\n")[0] || T("Heading");
    if (it.type === "timeline") return (it.label || "").split("\n")[0] || T("Timeline");
    let nm = it.name || ""; try { nm = nm || ((PLG[it.type] && PLG[it.type].info && PLG[it.type].info(id, it)) || {}).name || ""; } catch {}
    nm = nm || it.type; return !file ? nm : nm === file.split("/").pop() ? file : `${nm} · ${file}`;   // index.html says little: its path
  }
  // an element the arrow being drawn may end on: a picture, a card, a heading, a timeline or a group, not the note itself
  function dropEl(board, el, nid) {   // another note too: the arrow is a reply to it (2026-10-08)
    if (!el.matches || !el.matches(".it, .plg, .tx, .tl, .grp, .note") || !el.dataset.id || el.dataset.id === nid) return false;
    return el.classList.contains("grp") ? !!board.groups[el.dataset.id] : target(board.items[el.dataset.id]) || isNote(board.items[el.dataset.id]);
  }
  // «Notes from the board» in the Info of a card, as a picture has them (canvas.html infoCard): each note, how it is linked, a click goes to it
  function cardNotes(root, id) {
    const near = picIndex(), NN = [];
    for (const nid in board.items) { const n = board.items[nid]; if (n.type !== "note" || !(n.text || "").trim()) continue; const v = linksOf(nid, near).get(id); if (v) NN.push([nid, n, v]); }
    if (!NN.length) return;
    const VIA = { zone: T("in the area"), arrow: T("by an arrow"), overlap: T("lies on the card"), group: T("through the group"), reply: T("as a reply") };
    const s = document.createElement("section"), h = document.createElement("div"); s.className = "isec"; h.className = "sh";
    h.textContent = NN.length === 1 ? T("Note from the board") : `${T("Notes from the board")} · ${NN.length}`; s.appendChild(h);
    NN.forEach(([nid, n, v]) => {
      const b = document.createElement("button"); b.className = "inote"; b.style.setProperty("--nc", noteCol(n)[0]); b.title = T("Go to the note");
      b.innerHTML = `<div class="t">${mdHtml(n.text)}</div><div class="muted">${[...v].map(x => VIA[x] || x).join(", ")}</div>`;
      b.onclick = () => { goTo(nid); render(); }; s.appendChild(b);
    });
    root.appendChild(s);
  }
  // ---- the note dots on a thing (owner 2026-10-08: «each video shows only ONE blue dot» under two notes): one dot per note that links
  // it, in that note's colour, a row overlapping like avatars (each next one 60 % of a dot further, a ring of the board's colour
  // between), in the order the notes were made, so the newest is on top at the right; 4 at most and «+N». Hover: that note is outlined,
  // a click selects it. A reply's dot only on what it links itself, not on the things of the note it answers.
  const MAXD = 4, STEP = .6;
  // one pass over the notes: NL thing -> the colour for its old single-dot uses, HL the selected note's things, ND thing -> [note ids]
  function marks(board, sel, near, linksOf, noteCol) {
    const NL = new Map(), HL = new Map(), ND = new Map();
    for (const nid in board.items) {
      const nn = board.items[nid]; if (!isNote(nn)) continue; const c = noteCol(nn)[0], on = sel.has(nid);
      linksOf(nid, near).forEach((v, pid) => {
        if (on) HL.set(pid, c);
        if (v.size === 1 && v.has("reply")) return;
        if (!NL.has(pid) || on) NL.set(pid, c);
        if ((nn.to || []).includes(pid)) return;   // an arrow straight to it: its dot is the arrow's end (arrowSvg), not one more in the row
        (ND.get(pid) || ND.set(pid, []).get(pid)).push(nid);
      });
    }
    return { NL, HL, ND };
  }
  // the stack in a card's top left corner (a picture's .mk-note, a plugin's card gets one); redrawn only when its notes change
  function paintDots(el, nids) {
    let s = el.querySelector(":scope > .mk-note");
    if (!s) { s = document.createElement("span"); s.className = "mk mk-tl mk-note"; el.appendChild(s); }
    const L = nids || [], key = L.map(n => n + noteCol(board.items[n])[0]).join();
    if (s._k === key) return; s._k = key;
    const C = L.length > MAXD ? L.slice(0, MAXD) : L, more = L.length - C.length;
    s.innerHTML = C.map((n, k) => `<i data-nd="${n}" style="--c:${noteCol(board.items[n])[0]};--k:${k}" title="${escH(words(board.items[n].text, 8))}"></i>`).join("")
      + (more ? `<i class="more" data-nd="${L[MAXD]}" style="--k:${MAXD}" title="${escH(T("{n} more notes", { n: more }))}">+${more}</i>` : "");
  }
  let hotId = null;   // the note whose dot is under the pointer: outlined as an arrow's target is
  document.addEventListener("pointerover", e => {
    const d = e.target.closest && e.target.closest("[data-nd]"), id = d ? d.dataset.nd : null; if (id === hotId) return;
    const o = hotId && typeof EL !== "undefined" && EL.get(hotId); if (o) o.classList.remove("ndhot");
    hotId = id; const el = id && typeof EL !== "undefined" && EL.get(id); if (el) el.classList.add("ndhot");
  });
  // the far view's stack on its canvas, as the elements draw it: (x, y) the first dot's centre and r its radius in screen px
  let paper = { t: 0, c: "#111113" };
  function lodDots(g, x, y, r, ring, dpr, cols) {
    if (performance.now() - paper.t > 1000) paper = { t: performance.now(), c: getComputedStyle($("#stage") || document.documentElement).getPropertyValue("--board").trim() || paper.c };
    const C = cols.slice(0, MAXD), more = cols.length - C.length;
    const dot = (k, fill, ringCol) => { const cx = (x + k * r * 2 * STEP) * dpr; g.beginPath(); g.arc(cx, y * dpr, (r + ring) * dpr, 0, 7); g.fillStyle = ringCol; g.fill();
      g.beginPath(); g.arc(cx, y * dpr, r * dpr, 0, 7); g.fillStyle = fill; g.fill(); return cx; };
    C.forEach((c, k) => dot(k, c, k ? paper.c : "rgba(0,0,0,.6)"));
    if (!more) return;
    const cx = dot(MAXD, paper.c, paper.c); g.fillStyle = "#a1a1aa"; g.font = `600 ${Math.round(r * 1.1 * dpr)}px system-ui`;
    g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("+" + more, cx, y * dpr);
  }
  // ---- the arrows (owner 2026-10-08 on Concepts/html/notes-glass/a7-states.html «Arrow states»: «вот это очень круто, и по наведению
  // на линию или на точку можно было бы удалить»). A soft curve from the note's side facing the thing. On a thing a note's dot can sit
  // on (a picture, a video, a PDF, any card: caught) it ends at the note's own dot inside the thing's top left corner («End: dot inside»);
  // elsewhere (a group, a heading, a timeline, another note) on the thing's side with a head. Hovered: 3 px and a × under the pointer,
  // riding along the line with it, or beside the dot when the dot is hovered; the × removes the link (one undo step).
  // Where it starts and ends is board geometry only (owner 2026-10-08: «Если мы не двигаем элементы, линия не двигается, остается такой,
  // какая она, в зуме и в зум-ауте»): the end no longer jumped from the card's dot to its side when the card got too small for its
  // marks. Its sizes on screen (line, head, dot, ×) follow --z in CSS (canvas.html), so the arrows keep up with a zoom without a redraw
  // («оно пересчитывается, только когда остановили зум»), and far out the head and the dot shrink with the thing they end on instead of
  // covering it («стрелочки какие-то огромные»): --hmax and --rmax, from the thing's size.
  // anchor: the end of the k-th arrow (in board order) on thing box r: inside its top left corner, the next ones along its top
  const anchor = (r, k) => { const m = Math.min(r.w, r.h), c = Math.min(60, Math.max(6, m * .085)), g = Math.min(60, Math.max(10, m * .12));
    return { x: r.x + c + k * g, y: r.y + c }; };
  // the arrows' ends of a pass: note id + "|" + thing id -> its anchor, for every arrow that ends at a dot
  function anchors(board, rectOf) {
    const out = new Map(), on = new Map();
    for (const nid in board.items) {
      const n = board.items[nid]; if (!isNote(n)) continue;
      for (const t of n.to || []) {
        if (t === nid || !caught(board.items[t])) continue; const r = rectOf(t); if (!r) continue;
        const k = on.get(t) || 0; on.set(t, k + 1); out.set(nid + "|" + t, anchor(r, Math.min(k, MAXD)));
      }
    }
    let ix = null; out.near = r => (ix || (ix = index(board, rectOf, it => caught(it) || isNote(it))))(r);   // for the lines under them (arrowSvg)
    if (!cuts.next) queueMicrotask(flushCuts); cuts.next = [];
    return out;
  }
  const side = (r, p) => {   // the middle of r's side that faces p, with the way out of it
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2, dx = p.x - cx, dy = p.y - cy;
    return Math.abs(dx) * r.h >= Math.abs(dy) * r.w ? { x: dx > 0 ? r.x + r.w : r.x, y: cy, ux: dx > 0 ? 1 : -1, uy: 0 }
      : { x: cx, y: dy > 0 ? r.y + r.h : r.y, ux: 0, uy: dy > 0 ? 1 : -1 };
  };
  const bz = (P, t) => { const u = 1 - t, a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
    return { x: a * P[0].x + b * P[1].x + c * P[2].x + d * P[3].x, y: a * P[0].y + b * P[1].y + c * P[2].y + d * P[3].y }; };
  const HL = 11, HW = 5, DR = 9, XG = 10 / 24;   // the head's length and half width, the ×'s radius and its glyph's scale, screen px
  const deg = v => Math.round(Math.atan2(v.y, v.x) * 1800 / Math.PI) / 10;
  // ---- the line under the cards (owner 2026-10-08, after a sketch of options: «я бы сделал как сейчас, но линия проходила бы под самим
  // объектом»). The end stays the note's dot in the thing's corner, over it; the line goes under the thing it ends on and under every
  // other card and note it crosses, as if drawn in the board's layer below them (a heading's or a group's box is mostly empty: not
  // those). #links still lies over the cards (the dot, a head and the × must), so each arrow's line and hit band are clipped by the
  // boxes they cross: one clip path per arrow in board units, written with the markup, nothing per frame. The clip paths live in an
  // svg of their own outside the board's layers: a live zoom restyles every element of #links on each step (its --z), 400 arrows' clip
  // paths there cost 2-4 ms a zoom frame. A card or a note the note itself lies on keeps the line over it, so it still leaves the note.
  const crosses = (ax, ay, bx, by, r) => {   // the segment a-b meets box r: their boxes meet and r's corners are not all on one side of it
    const x1 = r.x + r.w, y1 = r.y + r.h; if ((ax < r.x && bx < r.x) || (ax > x1 && bx > x1) || (ay < r.y && by < r.y) || (ay > y1 && by > y1)) return false;
    const dx = bx - ax, dy = by - ay, a = dx * (r.y - ay) - dy * (r.x - ax), b = dx * (r.y - ay) - dy * (x1 - ax);
    const c = dx * (y1 - ay) - dy * (r.x - ax), d = dx * (y1 - ay) - dy * (x1 - ax);
    return !((a > 0 && b > 0 && c > 0 && d > 0) || (a < 0 && b < 0 && c < 0 && d < 0));
  };
  // boxes that overlap each other as boxes that don't (columns between their sides, each with its merged spans): an even-odd hole
  // counted twice would show the line again where two cards overlap
  function apart(rs) {
    if (!rs.some((a, i) => rs.some((b, j) => j > i && hit(a, b)))) return rs;
    const xs = [...new Set(rs.flatMap(r => [r.x, r.x + r.w]))].sort((a, b) => a - b), out = [];
    for (let i = 0; i + 1 < xs.length; i++) {
      const sp = rs.filter(r => r.x <= xs[i] && r.x + r.w >= xs[i + 1]).map(r => [r.y, r.y + r.h]).sort((a, b) => a[0] - b[0]), m = [];
      for (const s of sp) if (m.length && s[0] <= m[m.length - 1][1]) m[m.length - 1][1] = Math.max(m[m.length - 1][1], s[1]); else m.push(s.slice());
      for (const [y0, y1] of m) out.push({ x: xs[i], y: y0, w: xs[i + 1] - xs[i], h: y1 - y0 });
    }
    return out;
  }
  const N = 32, PAD = 1e5;   // the curve as 32 segments; the clip's outer box this far round it (the hit band is 16 px / zoom)
  function underCut(o, P, f) {
    const xs = new Float64Array(N + 1), ys = new Float64Array(N + 1); let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i <= N; i++) {
      const q = bz(P, i / N); xs[i] = q.x; ys[i] = q.y;
      if (q.x < x0) x0 = q.x; if (q.x > x1) x1 = q.x; if (q.y < y0) y0 = q.y; if (q.y > y1) y1 = q.y;
    }
    const k = o.key.indexOf("|"), nid = o.key.slice(0, k), t = o.key.slice(k + 1), rs = [];
    for (const { id, q } of o.ends.near({ x: x0, y: y0, w: x1 - x0, h: y1 - y0 })) {
      if (q.x > x1 || q.x + q.w < x0 || q.y > y1 || q.y + q.h < y0 || id === nid || (id !== t && hit(o.nr, q))) continue;
      for (let i = 0; i < N; i++) if (crosses(xs[i], ys[i], xs[i + 1], ys[i + 1], q)) { rs.push(q); break; }
    }
    if (!rs.length) return "";
    const box = (x, y, w, h) => `M${f(x)} ${f(y)}H${f(x + w)}V${f(y + h)}H${f(x)}Z`, id = "lkx-" + (o.cid || o.key).replace(/[^\w-]/g, c => "_" + c.charCodeAt(0).toString(16));
    // hy-allow: icon-inline a clip path, not an icon: the arrow's line is cut by the cards it crosses
    if (cuts.next) cuts.next.push(`<clipPath id="${id}" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" d="`
      + box(x0 - PAD, y0 - PAD, x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD) + apart(rs).map(r => box(r.x, r.y, r.w, r.h)).join("") + `"/></clipPath>`);
    return ` clip-path="url(#${id})"`;
  }
  // a pass of renderLinks (anchors() starts it) collects its clip paths; written once it is over, and only when they changed
  const cuts = { el: null, h: "", next: null };
  function flushCuts() {
    if (!cuts.next) return; const h = cuts.next.join(""); cuts.next = null; if (h === cuts.h) return;
    if (!cuts.el) {
      cuts.el = document.createElementNS("http://www.w3.org/2000/svg", "svg"); cuts.el.id = "linkcuts"; cuts.el.setAttribute("aria-hidden", "true");
      cuts.el.setAttribute("style", "position: absolute; width: 0; height: 0; overflow: hidden; pointer-events: none"); document.body.appendChild(cuts.el);
    }
    cuts.el.innerHTML = h; cuts.h = h;
  }
  // hy-allow-begin: icon-inline the board's own drawing, the notes' arrows; the × is the registry's «close»
  function arrowSvg(o) {   // o: key, on (its note selected), pick, col, nr, tr (boxes), ends (anchors()); board units throughout
    const { nr, tr } = o, dot = o.ends.get(o.key) || null, nc = { x: nr.x + nr.w / 2, y: nr.y + nr.h / 2 };
    const f = v => Math.round(v * 100) / 100, pt = q => `${f(q.x)} ${f(q.y)}`;
    let b, u;   // where it ends, and the way it comes in
    if (dot) b = { x: dot.x, y: dot.y };
    else if (holds(tr, nc)) {   // the note inside the frame it points at (a group): out to the frame's nearest side
      const c = [[tr.x, nc.y, -1, 0], [tr.x + tr.w, nc.y, 1, 0], [nc.x, tr.y, 0, -1], [nc.x, tr.y + tr.h, 0, 1]]
        .sort((p, q) => Math.hypot(p[0] - nc.x, p[1] - nc.y) - Math.hypot(q[0] - nc.x, q[1] - nc.y))[0];
      b = { x: c[0], y: c[1] }; u = { x: c[2], y: c[3] };
    } else { const e = side(tr, nc); b = { x: e.x, y: e.y }; u = { x: -e.ux, y: -e.uy }; }
    const a = side(nr, b);
    if (!u) u = a.ux ? { x: Math.sign(b.x - a.x) || a.ux, y: 0 } : { x: 0, y: Math.sign(b.y - a.y) || a.uy };
    const k = Math.hypot(b.x - a.x, b.y - a.y) * .4, P = [a, { x: a.x + a.ux * k, y: a.y + a.uy * k }, { x: b.x - u.x * k, y: b.y - u.y * k }, b];
    const d = `M${pt(P[0])}C${pt(P[1])} ${pt(P[2])} ${pt(P[3])}`, op = o.on || o.pick ? 1 : .8, m = Math.min(tr.w, tr.h);
    // a × at q; rot: the way back along the line from the dot, the × then sits that far from it on screen (.xo in canvas.html)
    const x = (cls, q, rot) => { const r = rot != null;
      return `<g class="del ${cls}" data-arrowdel="${o.key}" transform="translate(${pt(q)})${r ? ` rotate(${rot})` : ""}" style="color:${o.col}${r ? `;--th:${rot}` : ""}">`
        + `${r ? `<g class="xo">` : ""}<g class="xs"><title>${escH(T("Remove arrow"))}</title><circle r="${f(DR / XG)}" stroke-width="${f(2 / XG)}"/>`
        + `<path transform="translate(-12 -12)" d="${hyIconPath("close")}" stroke-width="${f(1.9 / XG)}" stroke-linecap="round"/></g>${r ? "</g>" : ""}</g>`; };
    // the caps far out: a dot at most 4.5 % of the thing's smaller side across its radius, a head at most 30 % of it long
    const cut = underCut(o, P, f);
    let h = `<g class="arw${o.pick ? " pick" : ""}${dot ? " ad" : ""}" data-k="${o.key}" style="--rmax:${f(m * .045)}px;--hmax:${f(m * .3 / HL)}">`
      + (cut ? `<g${cut}>` : "") + `<path class="hit" data-arrow="${o.key}" d="${d}" fill="none" stroke="transparent"/>`
      + `<path class="ln" d="${d}" fill="none" stroke="${o.col}" stroke-opacity="${op}" stroke-linecap="${dot ? "round" : "butt"}"/>` + (cut ? "</g>" : "");
    if (!dot) h += `<g transform="translate(${pt(b)}) rotate(${deg(u)})"><polygon class="hh" points="0 0 ${-HL} ${HW} ${-HL} ${-HW}" fill="${o.col}" fill-opacity="${op}"/></g>`;
    h += x("m", bz(P, .5));
    // the dot is the note's dot on the thing: hover outlines the note, a click selects it, and its × sits beside it, back along the line
    if (dot) h += `<circle class="hit hd" data-nd="${o.key.split("|")[0]}" cx="${f(b.x)}" cy="${f(b.y)}" fill="${o.col}"/>`
      + x("e", b, deg({ x: P[2].x - b.x, y: P[2].y - b.y }));
    return h + "</g>";
  }
  // hy-allow-end
  // the × under the pointer while it moves along a line (owner 2026-10-08: «Почему я теперь не могу водить по линии мышкой? ... Я хочу,
  // чтобы я мог водить мышкой, и у меня был этот символ удалить связь»): at the line's point nearest the pointer, so a click anywhere
  // on the line takes the arrow off, as one click on its × did (2026-10-02: no select-then-Delete); the pointer on the × holds it still
  document.addEventListener("pointermove", e => {
    const g = e.target.closest && e.target.closest("#links .arw"); if (!g || e.target.closest(".del") || typeof toWorld !== "function") return;
    const ln = g.querySelector(".ln"), xm = g.querySelector(".del.m"); if (!ln || !xm) return;
    const p = toWorld(e.clientX, e.clientY), L = ln.getTotalLength(), N = 40, dist = l => { const q = ln.getPointAtLength(l); return (q.x - p.x) ** 2 + (q.y - p.y) ** 2; };
    let best = 0; for (let i = 1, bd = dist(0); i <= N; i++) { const v = dist(L * i / N); if (v < bd) { bd = v; best = i; } }
    let lo = Math.max(0, best - 1) * L / N, hi = Math.min(N, best + 1) * L / N;
    for (let i = 0; i < 12; i++) { const a = lo + (hi - lo) / 3, b = hi - (hi - lo) / 3; if (dist(a) < dist(b)) hi = b; else lo = a; }
    const q = ln.getPointAtLength((lo + hi) / 2);
    xm.setAttribute("transform", `translate(${Math.round(q.x * 100) / 100} ${Math.round(q.y * 100) / 100})`);
  });
  window.hyNoteLink = { target, caught, kind, index, links, what, meta, label, dropEl, cardNotes, WORD,
    replyOf, replies, circle, reply, chain, chainSvg, replyInfo, marks, paintDots, lodDots, placeReply, anchors, arrowSvg, underCut, side, bz, holds };   // the last four: ui/connectors.js
})();
