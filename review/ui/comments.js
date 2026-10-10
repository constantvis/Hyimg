// Annotations on the board, as Figma's comments (owner 2026-10-07: «добавлять комменты, как в Figma ... возможность тегать участников»;
// 2026-10-09: «сделай вместо комментариев Annotations»: the interface says Annotation, the code, the server and hy.py still «comment»). A
// click with the Annotation tool (C on the board, ui/anncore.js) on an object or on empty canvas drops a pin with a thread: text with
// @mentions (people this Mac knows, «@Claude» = your own Claude, «@Codex · Name» another person's agent), replies, edit and delete of
// your own, Resolve and Reopen, and the list of the page's comments (open or resolved, by person, a click goes to the pin). A pin wears
// its author's face, an agent's comment the agent's badge on its person's face. A pin on an object moves with it (ui/anncore.js
// anchorAt). Each action is one undo step. The bell names others' comments and every mention of you or your agents (review/comments.py).
(() => {
  if (window.hyComments) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)));
  const $ = q => document.querySelector(q);
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const C = { threads: new Map(), page: null, open: null, draft: null, filter: "open", person: "", busy: false, lit: new Set(), drafts: new Map(), waits: new Map(), wn: 0 };
  const AN = () => window.hyAnnot;
  const ok = () => typeof board !== "undefined" && typeof BOARD !== "undefined" && !!AN();
  const clone = o => JSON.parse(JSON.stringify(o));
  const ago = iso => (window.T && window.T.ago ? window.T.ago(iso) : iso);

  async function load() {
    if (!ok()) return;
    const page = BOARD;
    try {
      const d = await AN().api("/api/comments?name=" + encodeURIComponent(page));
      if (page !== BOARD) return;
      const was = C.open && !C.draft ? C.threads.get(C.open) : null;
      C.threads = new Map((d.items || []).map(t => [t.id, t])); C.page = page;
      if (was && !C.threads.has(was.id)) gone(was);   // deleted elsewhere (P4 B-33)
      draw(); changed(); if (C.open && !C.draft) thread(C.open);
      if ($("#cmlist.open")) list(true);
      AN().paintBar();
    } catch {}
  }
  async function send(body) {
    const d = await AN().api("/api/comments", { name: BOARD, ...body });
    if (d.thread && !d.deleted) C.threads.set(d.thread.id, d.thread);
    if (d.deleted) { C.threads.delete(d.deleted); if (C.open === d.deleted) close(); C.drafts.delete(d.deleted); }
    draw(); changed(); if (C.open && C.threads.has(C.open)) thread(C.open); if ($("#cmlist.open")) list(true); AN().paintBar();
    return d;
  }
  // one undo step: the thread as it was before, as it is after (null: none); undo and redo send it back whole (op put), refused when
  // someone changed it since (base: the updated the server must still have; base_rev its rev, exact where updated is whole seconds and two
  // edits in one second looked the same, П4 audit 2026-10-10)
  function stepOf(before, after) {
    const mark = t => t ? { base: t.updated, base_rev: t.rev } : {};
    let last = mark(after);
    const go = async t => { const d = await send({ op: "put", id: (before || after).id, thread: t, ...last }); last = mark(d.thread && !d.deleted ? d.thread : null); };
    AN().step({ undo: () => go(before && clone(before)), redo: () => go(after && clone(after)) });
  }
  async function act(body, before) {
    try { const d = await send(body); stepOf(before || null, d.deleted ? null : d.thread); return d; }
    catch (ex) { AN().fail(ex); return null; }
  }

  // ---- pins ----------------------------------------------------------------------------------------------------------------------
  // a plugin may place a pin itself (Dev mode: the element's place in the live page, hyComments.position(fn)); else its share of the card
  const PLACE = [];
  const placed = t => {   // {p} when a plugin says where (p null: nowhere now), else null
    for (const f of PLACE) { try { const p = f(t); if (p !== undefined) return { p }; } catch (ex) { console.error("comment place", ex); } }
    return null;
  };
  const still = t => {
    const a = areaBox(t); if (a) return { x: a.x + a.w, y: a.y };   // an area's pin stands on its top right corner
    if (!t.anchor) return { x: t.at[0], y: t.at[1] }; const q = AN().boxOf(t.anchor); return q ? { x: q.x + t.at[0] * q.w, y: q.y + t.at[1] * q.h } : null;
  };
  const where = t => { const q = placed(t); return q ? q.p : still(t); };
  // an element's thread on an HTML card whose point lies past the card's picture (the page's first screen, Dev Studio): its pin waits at
  // the picture's edge (at is held at y 0.98), the pin's tooltip says where the element is (owner 2026-10-08: a tree row far down the page)
  const beyond = t => {
    const e = t.element, it = e && Array.isArray(e.page) && t.anchor && board.items[t.anchor.obj]; if (!it || !it.vw || !it.w || !it.h) return "";
    return e.page[1] > it.vw * it.h / it.w ? " · " + T("further down the page") : e.page[0] > it.vw ? " · " + T("further right on the page") : "";
  };
  // a comment's area in board units: shares of its object's box, or board units when it lies on the empty board
  function areaBox(t) {
    if (!t.area) return null; const [u, v, w, h] = t.area;
    if (!t.anchor) return { x: u, y: v, w, h };
    const q = AN().boxOf(t.anchor); return q ? { x: q.x + u * q.w, y: q.y + v * q.h, w: w * q.w, h: h * q.h } : null;
  }
  const colorOf = by => { const P = (window.hyPeople && hyPeople.people()) || {}, c = (P[(by || {}).person] || {}).color; return (window.HY_COLORS || {})[c] || ""; };
  const pctR = a => `x ${Math.round(a[0] * 100)}–${Math.round((a[0] + a[2]) * 100)} %, y ${Math.round(a[1] * 100)}–${Math.round((a[1] + a[3]) * 100)} %`;
  const changed = () => { try { window.dispatchEvent(new CustomEvent("hy-comments")); } catch {} };
  const face = (by, size) => (window.hyAvatarOf ? hyAvatarOf(by, size) : "");
  const shown = t => AN().visible(t.by) && (!t.resolved || C.open === t.id);
  function pins() {
    let el = document.getElementById("cmpins");
    if (!el && $("#world")) {
      el = document.createElement("div"); el.id = "cmpins"; $("#world").appendChild(el);
      el.addEventListener("pointerdown", e => { const p = e.target.closest(".cmpin"); if (!p) return; e.stopPropagation(); e.preventDefault(); pinDrag(e, p.dataset.c); });
    }
    return el;
  }
  function draw() {
    if (!ok()) return;
    if (C.page !== BOARD) { C.threads = new Map(); C.page = BOARD; close(); load(); }
    const el = pins(); if (!el) return;
    el.classList.toggle("off", !AN().state.show);
    const want = new Map();
    for (const t of C.threads.values()) {
      if (!shown(t)) continue; const q = placed(t), p = q ? q.p : still(t); if (!p) continue;
      const n = t.messages.length - 1, off = q ? "" : beyond(t);   // on the still: the element further down says so
      want.set(t.id, [p, `${face(t.by, 24)}${n ? `<b class="cmp-n">${n}</b>` : ""}${C.drafts.has(t.id) && C.open !== t.id ? DOT : ""}`,
        `${window.hyWhoText ? hyWhoText(t) : ""}: ${t.messages[0].text.slice(0, 80)}${off}`]);
    }
    for (const [k, w] of C.waits) if (w.d.page === BOARD && !(C.draft && C.draft.wid === k)) want.set(k, [w.d.pos, face(AN().state.me(), 24) + DOT, T("Draft: {text}", { text: w.text.slice(0, 80) })]);
    if (C.draft) want.set("draft", [C.draft.pos, face(AN().state.me(), 24), T("New annotation")]);
    drawAreas(el);
    for (const p of [...el.querySelectorAll(":scope > .cmpin")]) if (!want.has(p.dataset.c)) p.remove();
    for (const [id, [p, h, title]] of want) {
      let b = el.querySelector(`:scope > [data-c="${id}"]`);
      if (!b) { b = document.createElement("button"); b.className = "cmpin hy-apin face"; b.dataset.c = id; el.appendChild(b); }   // ui/hy/apin.css
      if (b._h !== h) { b.innerHTML = h; b._h = h; }
      own(b, id);
      b.title = title; b.style.left = p.x + "px"; b.style.top = p.y + "px";
      b.classList.toggle("on", C.open === id || (id === "draft")); b.classList.toggle("done", !!(C.threads.get(id) || {}).resolved);
      b.classList.toggle("lit", C.lit.has(id));
    }
  }
  // the areas (owner 2026-10-07: «выделяешь область и пишешь, что к чему», as the library's preview): a thin outline in its author's colour,
  // lit while its thread is open or its pin or list row is pointed at
  function drawAreas(el) {
    const want = new Map();
    for (const t of C.threads.values()) { if (!shown(t)) continue; const a = areaBox(t); if (a) want.set(t.id, [a, colorOf(t.by)]); }
    if (C.draft && C.draft.box) want.set("draft", [C.draft.box, colorOf(AN().state.me())]);
    if (C.live) want.set("live", [C.live, colorOf(AN().state.me())]);
    for (const d of [...el.querySelectorAll(":scope > .cmarea")]) if (!want.has(d.dataset.a)) d.remove();
    for (const [id, [a, c]] of want) {
      let d = el.querySelector(`:scope > .cmarea[data-a="${id}"]`);
      if (!d) { d = document.createElement("div"); d.className = "cmarea"; d.dataset.a = id; el.prepend(d); }
      Object.assign(d.style, { left: a.x + "px", top: a.y + "px", width: a.w + "px", height: a.h + "px" }); if (c) d.style.setProperty("--ac", c);
      own(d, id);
      d.classList.toggle("on", C.open === id || id === "draft" || id === "live" || C.hov === id);
    }
  }
  // the object a thread's pin and area belong to ("" the board itself; none on a draft): a Studio lays the others under its card (ui/editlift.js)
  function own(el, id) {
    const t = C.threads.get(id), o = t ? (t.anchor && t.anchor.obj) || "" : null;
    if (o == null) delete el.dataset.o; else if (el.dataset.o !== o) el.dataset.o = o;
  }
  function hover(id) { if (C.hov === id) return; C.hov = id; const el = pins(); if (el) drawAreas(el); }
  // pins lit from outside the board: Dev Studio's tree lights the pins of the row under the pointer (owner 2026-10-08)
  function light(ids) {
    C.lit = new Set(ids || []); const el = pins(); if (!el) return;
    for (const b of el.querySelectorAll(":scope > .cmpin")) b.classList.toggle("lit", C.lit.has(b.dataset.c));
  }
  // the Comment tool: a click drops a pin, a drag draws an area on the object under it (or the empty board) and opens the box at once
  const tool = {
    down(e, p) { if (C.draft || C.open) { close(); C.skip = true; return; } C.drag = { p0: p, x: e.clientX, y: e.clientY }; },
    move(e, p) {
      const d = C.drag; if (!d || (!d.on && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 5)) return; d.on = true;
      C.live = { x: Math.min(d.p0.x, p.x), y: Math.min(d.p0.y, p.y), w: Math.abs(p.x - d.p0.x), h: Math.abs(p.y - d.p0.y) }; draw();
    },
    up(e, p) {
      if (C.skip) { C.skip = false; return; }
      const d = C.drag, r = C.live; C.drag = null; C.live = null; if (!d) return;
      if (!d.on || !r || r.w * cam.z < 6 || r.h * cam.z < 6) { newAt(d.p0); return; }
      const at = AN().anchorAt(r), q = at.anchor && AN().boxOf(at.anchor), corner = { x: r.x + r.w, y: r.y };
      const area = q ? [(r.x - q.x) / q.w, (r.y - q.y) / q.h, r.w / q.w, r.h / q.h].map(v => Math.round(v * 1e5) / 1e5) : [r.x, r.y, r.w, r.h].map(Math.round);
      newAt(corner, { anchor: at.anchor, at: q ? [area[0] + area[2], area[1]] : [corner.x, corner.y], area, box: r });
    },
  };
  // a press on a pin opens its thread; a drag moves it (onto another object or the canvas), one undo step
  function pinDrag(e, id) {
    if (id === "draft") return;
    const w = C.waits.get(id); if (w) { newAt(w.d.pos, { ...w.d, wid: id, text: w.text, ment: w.ment }); return; }   // a new one not sent: open again
    const t = C.threads.get(id); if (!t) return;
    const s = { x: e.clientX, y: e.clientY }; let moved = false;
    const mv = ev => {
      if (!moved && Math.hypot(ev.clientX - s.x, ev.clientY - s.y) < 4) return; moved = true;
      const p = toWorld(ev.clientX, ev.clientY), b = document.querySelector(`#cmpins [data-c="${id}"]`); if (b) { b.style.left = p.x + "px"; b.style.top = p.y + "px"; }
    };
    const end = ev => {
      removeEventListener("pointermove", mv, true); removeEventListener("pointerup", end, true);
      if (!moved) { C.open === id ? close() : thread(id); return; }
      const p = toWorld(ev.clientX, ev.clientY), at = AN().anchorAt({ x: p.x, y: p.y, w: 0, h: 0 });
      act({ op: "move", id, anchor: at.anchor, at: at.rel(p.x, p.y) }, clone(t));
    };
    addEventListener("pointermove", mv, true); addEventListener("pointerup", end, true);
  }

  // ---- the thread --------------------------------------------------------------------------------------------------------------
  function pop() {
    let el = document.getElementById("cmthread");
    if (!el) {
      el = document.createElement("div"); el.id = "cmthread"; el.className = "cm-pop"; el.setAttribute("role", "dialog");
      stage.appendChild(el);
      ["pointerdown", "wheel"].forEach(k => el.addEventListener(k, e => e.stopPropagation(), { passive: true }));
      el.addEventListener("click", click); el.addEventListener("input", typed);
      // the board's one rule for fields (ui/typing.js): ↵ sends, ⇧↵ a new line, Esc keeps the words as a draft on the pin, an IME's ↵ is its own
      const apply = e => (e.key === "Escape" ? leave() : e.target.matches("textarea") ? submit() : e.target.click());
      if (window.hyTyping && hyTyping.keys) hyTyping.keys(el, { esc: "apply", tab: "own", before: mentionKey, apply }); else el.addEventListener("keydown", key);
      // the field's ↵ in its corner while it is written in (ui/boardhints.js «comment», owner 2026-10-09: «просто Enter символа достаточно»)
      el.addEventListener("focusin", e => { if (e.target.matches("textarea") && window.hyHint) C.kh = hyHint("comment", e.target); });
      el.addEventListener("focusout", e => { if (C.kh && !el.contains(e.relatedTarget)) { C.kh.hide(); C.kh = null; } });
    }
    return el;
  }
  const me = () => (window.hyPeople && hyPeople.me()) || null;
  const mine = by => !!me() && (by || {}).person === me().id;
  function text(m) {   // the words with their @mentions lit, line breaks kept
    let h = esc(m.text);
    for (const x of [...(m.mentions || [])].sort((a, b) => (b.label || "").length - (a.label || "").length)) {
      if (!x.label) continue;
      h = h.split("@" + esc(x.label)).join(`<span class="cm-at" data-p="${esc(x.person)}">@${esc(x.label)}</span>`);
    }
    return h.replace(/\n/g, "<br>");
  }
  function msg(m) {
    const own = mine(m.by), w = window.hyWhoText ? hyWhoText(m) : "";
    return `<div class="cm-m" data-m="${esc(m.id)}">${face(m.by, 24)}<div class="cm-b"><div class="cm-mh"><b>${esc(w)}</b><time>${esc(ago(m.created))}`
      + `${m.edited ? " · " + esc(T("edited")) : ""}</time>${own ? `<span class="cm-own"><hy-icon-button icon="editText" size="xs" label="${esc(T("Edit"))}" data-cm="edit">`
      + `</hy-icon-button><hy-icon-button icon="trash" size="xs" label="${esc(T("Delete"))}" data-cm="del"></hy-icon-button></span>` : ""}</div>`
      + `<div class="cm-tx">${text(m)}</div></div></div>`;
  }
  function composer(ph) {
    return `<div class="cm-c"><textarea rows="1" maxlength="4000" placeholder="${esc(ph)}" aria-label="${esc(ph)}"></textarea>`
      + `<hy-icon-button icon="send" size="s" variant="solid" label="${esc(T("Send"))} · ↵" data-cm="send"></hy-icon-button></div>`;
  }
  function thread(id) {
    const t = C.threads.get(id); if (!t) return;
    if (C.draft) cancelDraft();
    // the refresh every 8 s draws an open thread anew: the field being typed in keeps its text, focus and caret, or the next keys went to
    // the board (owner 2026-10-10: «когда я в аннотациях пишу что-то, у меня триггерится F кнопка»: F ♥ the selected, N a new note)
    if (C.open !== id) stash();   // another thread was open: its words stay with it
    const old = C.open === id ? pop().querySelector("textarea") : null, back = old ? null : C.drafts.get(id), keep = old ? old.value : back ? back.text : "";
    const caret = old && document.activeElement === old ? [old.selectionStart, old.selectionEnd, old.selectionDirection] : null;
    const fresh = C.open !== id;
    C.open = id; C.ment = old ? C.ment || [] : back ? back.ment.map(q => ({ ...q })) : [];
    if (old) mentionsOff();   // drawn anew (the 8 s refresh): the mention list goes too, a hidden one took the next ↵ (P4 B-12)
    const el = pop(), what = t.element ? t.element.css || t.element.tag || "" : partName(t.anchor) || (t.anchor ? (window.hyNoteLink && board.items[t.anchor.obj]
      ? hyNoteLink.label(board, t.anchor.obj) : t.anchor.file || "") : "");
    el.innerHTML = `<div class="cm-h"><b>${esc(T("Annotation"))}</b>${what ? `<span class="cm-w" title="${esc(what)}">· ${esc(what.split("/").pop())}</span>` : ""}`
      + `<span class="cm-sp"></span><hy-icon-button icon="${t.resolved ? "reset" : "resolve"}" size="s" label="${esc(t.resolved ? T("Reopen") : T("Resolve"))}"`
      + ` data-cm="${t.resolved ? "reopen" : "resolve"}"${t.resolved ? "" : ' class="cm-rs"'}></hy-icon-button>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Close"))} · Esc" data-cm="close"></hy-icon-button></div>`
      + (t.resolved ? `<div class="hy-hint cm-rd">${T("Resolved by <b>{who}</b>", { who: esc(window.hyWhoText ? hyWhoText(t.resolved) : "") })}</div>` : "")
      + `<div class="cm-msgs">${t.messages.map(msg).join("")}</div>` + composer(T("Reply…"));
    el.classList.add("open"); el.dataset.c = id;
    const ta = el.querySelector("textarea"); ta.value = keep; grow(ta); if (old && C.edit) ta.placeholder = old.placeholder;
    if (caret) { ta.focus({ preventScroll: true }); ta.setSelectionRange(...caret); }
    follow(); draw();
    const box = el.querySelector(".cm-msgs"); box.scrollTop = box.scrollHeight;
    // a thread opened anew says so (Dev Studio's tree selects its element's row); made: the one just written, its row is where it was
    if (fresh) try { window.dispatchEvent(new CustomEvent("hy-comment-open", { detail: { id, thread: t, made: C.made === id } })); } catch {}
  }
  // a new thread at board point p; o: {anchor, at, element} when the caller knows better (Dev mode: an element of the page), cancel: called
  // when the box closes unsent
  function newAt(p, o) {
    const at = AN().anchorAt({ x: p.x, y: p.y, w: 0, h: 0 });
    close();
    C.draft = o ? { anchor: o.anchor || null, at: o.at, element: o.element || null, area: o.area || null, box: o.box || null, pos: p,
      cancel: typeof o.cancel === "function" ? o.cancel : null }   // cancel: the draft closed unsent (Dev Studio gives back a scroll)
      : { anchor: at.anchor, at: at.rel(p.x, p.y), pos: p };
    C.draft.page = (o && o.page) || BOARD; C.draft.wid = (o && o.wid) || null;   // wid: a kept draft opened again
    C.ment = o && o.ment ? o.ment.map(q => ({ ...q })) : [];
    const el = pop();
    const what = C.draft.element ? C.draft.element.css || C.draft.element.tag || "" : partName(C.draft.anchor);
    el.innerHTML = `<div class="cm-h"><b>${esc(T("New annotation"))}</b>${what ? `<span class="cm-w" title="${esc(what)}">· ${esc(what)}</span>` : ""}<span class="cm-sp"></span>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Cancel"))} · Esc" data-cm="close"></hy-icon-button></div>`
      + composer(C.draft.area ? T("Annotation on area {n}", { n: areaN(C.draft.anchor) }) : T("Add an annotation… @ to mention"));
    el.classList.add("open"); el.dataset.c = "draft";
    if (o && o.text) { const ta = el.querySelector("textarea"); ta.value = o.text; grow(ta); }
    follow(); draw(); el.querySelector("textarea").focus(); setTimeout(() => { const ta = el.querySelector("textarea"); if (ta && document.activeElement !== ta) ta.focus(); }, 0);
  }
  // a Studio's thread names its layer or 3D object in the header (anchor.part, review/comments.py clean_part)
  const partName = an => (an && an.part && (an.part.name || an.part.id)) || "";
  const areaN = an => 1 + [...C.threads.values()].filter(t => t.area && (an ? t.anchor && t.anchor.obj === an.obj : !t.anchor)).length;
  // Unsent words stay (P4 B-03, B-04): every way out of a thread or a new annotation (Esc, a press on the board, another pin, the dock's
  // button, a page switch) keeps what was typed as a draft on its pin, with a small dot; opening the pin again brings the words back.
  // Nothing is ever sent by leaving. An edit of a message is not kept: leaving it gives back the reply written before it (B-11)
  const DOT = '<i class="hy-dot cmp-d"></i>';
  const keepFor = (id, v) => { if (v && v.text.trim()) C.drafts.set(id, v); else C.drafts.delete(id); };
  function stash() {
    const ta = document.querySelector("#cmthread.open textarea"); if (!ta) return;
    const text = ta.value, ment = (C.ment || []).filter(m => text.includes("@" + m.label));
    if (C.edit) { if (C.open) keepFor(C.open, C.editKeep); C.edit = null; C.editKeep = null; return; }
    if (C.draft) {
      const k = C.draft.wid || "w" + ++C.wn;
      if (text.trim()) { C.waits.set(k, { d: { ...C.draft }, text, ment }); C.draft.wid = k; } else C.waits.delete(k);
    } else if (C.open) keepFor(C.open, { text, ment });
  }
  function close() {
    stash();
    const el = document.getElementById("cmthread"); if (el) { el.classList.remove("open"); el.innerHTML = ""; }
    const dr = C.draft; C.open = null; C.draft = null; mentionsOff(); draw();
    unsent(dr);
  }
  // the open thread was deleted elsewhere (another window, an agent): it closes and says so; words typed in it stay as a new draft where
  // its pin stood (P4 B-33: it stayed open and ↵ threw an error)
  function gone(t) {
    const ta = document.querySelector("#cmthread.open textarea"), text = ta ? ta.value : "", ment = (C.ment || []).filter(m => text.includes("@" + m.label));
    C.drafts.delete(t.id); C.edit = null; C.editKeep = null; C.open = null; const el = document.getElementById("cmthread"); if (el) { el.classList.remove("open"); el.innerHTML = ""; }
    mentionsOff();
    const r = stage.getBoundingClientRect(), pos = still(t) || toWorld(r.left + r.width / 2, r.top + r.height / 2), an = t.anchor && board.items[t.anchor.obj] ? t.anchor : null;
    if (text.trim()) C.waits.set("w" + ++C.wn, { d: { anchor: an, at: an ? t.at : [pos.x, pos.y], area: null, pos, page: BOARD }, text, ment });
    if (typeof toast === "function") toast(T(text.trim() ? "This annotation was deleted elsewhere, your words are kept as a draft" : "This annotation was deleted elsewhere"), "info");
  }
  function unsent(dr) { if (dr && dr.cancel) try { dr.cancel(); } catch (ex) { console.error("comment cancel", ex); } }
  function cancelDraft() { if (C.draft) close(); }
  function follow() {   // the open thread stands beside its pin, wherever the camera goes
    const el = document.getElementById("cmthread"); if (!el || !el.classList.contains("open") || typeof cam === "undefined") return;
    const t = C.threads.get(C.open), p = C.draft ? C.draft.pos : t && where(t); if (!p) return;
    const r = stage.getBoundingClientRect(), x = (p.x - cam.x) * cam.z, y = (p.y - cam.y) * cam.z, w = el.offsetWidth, h = el.offsetHeight;
    // a Studio keeps it in its free part, off its side panels (hyComments.bounds, the window's px)
    let l0 = 12, r0 = r.width - 12, t0 = 58, b0 = r.height - 12; const fb = C.bounds && C.bounds();
    if (fb) { l0 = Math.max(l0, fb.l - r.left); r0 = Math.min(r0, fb.r - r.left); t0 = Math.max(t0, fb.t - r.top); b0 = Math.min(b0, fb.b - r.top); }
    let left = x + 40, top = y - 40;
    if (left + w > r0) left = x - w - 16;
    el.style.left = Math.max(l0, Math.min(r0 - w, left)) + "px"; el.style.top = Math.max(t0, Math.min(b0 - h, top)) + "px";
  }
  async function submit() {
    const el = pop(), ta = el.querySelector("textarea"), v = (ta && ta.value || "").trim(); if (!v || C.busy) return;
    const ment = (C.ment || []).filter(m => v.includes("@" + m.label));
    C.busy = true; let after = [];
    try {
      if (C.draft) {
        const d = C.draft; C.draft = null;
        const res = await act({ op: "new", anchor: d.anchor, at: d.at, element: d.element, area: d.area, text: v, mentions: ment });
        if (res && res.thread) { if (d.wid) C.waits.delete(d.wid); C.made = res.thread.id; thread(res.thread.id); C.made = null; const ta = pop().querySelector("textarea"); if (ta) ta.focus(); }
        else { C.draft = d; close(); }   // not sent: the words stay as a draft
      } else if (C.open) {
        const before = clone(C.threads.get(C.open));
        if (C.edit) {   // the reply written before the edit comes back into the field
          const mid = C.edit, k = C.editKeep; C.edit = null; C.editKeep = null; ta.value = k ? k.text : ""; after = k ? k.ment : [];
          await act({ op: "edit", id: C.open, mid, text: v, mentions: ment }, before);
        } else { ta.value = ""; C.drafts.delete(C.open); await act({ op: "reply", id: C.open, text: v, mentions: ment }, before); }
        if (C.open) { thread(C.open); const t2 = pop().querySelector("textarea"); if (t2) t2.focus(); }
      }
    } finally { C.busy = false; C.ment = after; }
  }
  function click(e) {
    const b = e.target.closest("[data-cm]"); if (!b) { if (e.target.closest(".cm-at")) return; return; }
    const k = b.dataset.cm, t = C.threads.get(C.open), m = b.closest("[data-m]");
    if (k === "close") { close(); return; }
    if (k === "send") { submit(); return; }
    if (k === "pick") { pickMention(+b.dataset.i); return; }
    if (!t) return;
    if (k === "resolve" || k === "reopen") { act({ op: k, id: t.id }, clone(t)).then(() => { if (k === "resolve") close(); }); return; }
    if (k === "del" && m) { act({ op: "delete", id: t.id, mid: m.dataset.m }, clone(t)); return; }
    if (k === "edit" && m) {
      const x = t.messages.find(q => q.id === m.dataset.m), ta = pop().querySelector("textarea"); if (!x || !ta) return;
      if (!C.edit) C.editKeep = { text: ta.value, ment: (C.ment || []).map(q => ({ ...q })) };   // the reply being written, given back after the edit
      C.edit = x.id; C.ment = (x.mentions || []).map(q => ({ ...q })); ta.value = x.text; ta.placeholder = T("Edit the annotation…"); grow(ta); ta.focus();
    }
  }
  function mentionKey(e) {   // the mention list open: its arrows, ↵, Tab and Esc are its own
    if (!AT.list.length || !["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(e.key)) return false;
    e.preventDefault();
    if (e.key === "Escape") { mentionsOff(); return true; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { AT.i = (AT.i + (e.key === "ArrowDown" ? 1 : -1) + AT.list.length) % AT.list.length; paintAt(); return true; }
    pickMention(AT.i); return true;
  }
  function leave() {   // an edit: its words go, the reply written before it comes back (P4 B-11); else close, the words kept as a draft
    if (!C.edit) { close(); return; }
    const k = C.editKeep || { text: "", ment: [] }; C.edit = null; C.editKeep = null; pop().querySelector("textarea").value = k.text; C.ment = k.ment; thread(C.open);
  }
  function key(e) {   // a page without ui/typing.js
    e.stopPropagation(); if (e.isComposing || e.keyCode === 229 || mentionKey(e)) return;
    if (e.key === "Enter" && !e.shiftKey && e.target.matches("textarea")) { e.preventDefault(); submit(); return; }
    if (e.key === "Escape") { e.preventDefault(); leave(); }
  }
  const grow = ta => { ta.style.height = "auto"; ta.style.height = Math.min(140, ta.scrollHeight) + "px"; };

  // ---- @mentions -------------------------------------------------------------------------------------------------------------------
  const AT = { list: [], i: 0, from: 0 };
  function candidates() {
    const P = (window.hyPeople && hyPeople.people()) || {}, m = me(), out = [], AG = window.HY_AGENTS;
    if (m && AG) for (const k of AG.CATALOG.filter(k => k !== "agent")) out.push({ label: AG.label(k), person: m.id, agent: k, by: { person: m.id, via: k }, sub: T("your agent") });
    for (const [id, p] of Object.entries(P)) {
      if (p.me || p.hidden) continue;
      out.push({ label: p.name, person: id, by: { person: id, via: "app" }, sub: "" });
      for (const k of Object.keys(p.agents || {})) {
        if (AG) out.push({ label: `${AG.label(k)} · ${p.name}`, person: id, agent: k, by: { person: id, via: k }, sub: T("{name}'s agent", { name: p.name }) });
      }
    }
    return out;
  }
  function typed(e) {
    const ta = e.target; if (!ta.matches("textarea")) return;
    grow(ta);
    const before = ta.value.slice(0, ta.selectionStart), m = before.match(/(^|\s)@([^\s@]{0,30})$/);
    if (!m) { mentionsOff(); return; }
    const q = m[2].toLowerCase();
    AT.list = candidates().filter(c => c.label.toLowerCase().split(/[\s·]+/).some(w => w.startsWith(q)) || c.label.toLowerCase().startsWith(q)).slice(0, 8);
    AT.i = 0; AT.from = before.length - m[2].length - 1;
    paintAt();
  }
  function paintAt() {
    let el = document.getElementById("cmat");
    if (!AT.list.length) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement("div"); el.id = "cmat"; el.setAttribute("role", "listbox"); pop().appendChild(el); el.addEventListener("pointerdown", e => e.preventDefault()); }
    el.innerHTML = AT.list.map((c, i) => `<button role="option" aria-selected="${i === AT.i}" data-cm="pick" data-i="${i}">${face(c.by, 20)}<span>${esc(c.label)}</span>`
      + `${c.sub ? `<i>${esc(c.sub)}</i>` : ""}</button>`).join("");
  }
  function pickMention(i) {
    const c = AT.list[i], ta = pop().querySelector("textarea"); if (!c || !ta) return;
    const end = ta.selectionStart, word = "@" + c.label + " ";
    ta.value = ta.value.slice(0, AT.from) + word + ta.value.slice(end);
    const at = AT.from + word.length; ta.setSelectionRange(at, at); ta.focus();
    (C.ment = C.ment || []).push({ person: c.person, ...(c.agent ? { agent: c.agent } : {}), label: c.label });
    mentionsOff(); grow(ta);
  }
  function mentionsOff() { AT.list = []; const el = document.getElementById("cmat"); if (el) el.remove(); }

  // ---- the list of the page's comments --------------------------------------------------------------------------------------------
  function list(refresh) {
    let el = document.getElementById("cmlist");
    if (el && el.classList.contains("open") && !refresh) { el.classList.remove("open"); return; }
    if (!el) {
      el = document.createElement("div"); el.id = "cmlist"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", T("Annotations")); stage.appendChild(el);
      ["pointerdown", "wheel"].forEach(k => el.addEventListener(k, e => e.stopPropagation(), { passive: true }));
      el.addEventListener("click", e => {
        const f = e.target.closest("[data-cf]"); if (f) { C.filter = f.dataset.cf; list(true); return; }
        const p = e.target.closest("[data-cp]"); if (p) { C.person = C.person === p.dataset.cp ? "" : p.dataset.cp; list(true); return; }
        if (e.target.closest("[data-cm=closelist]")) { el.classList.remove("open"); return; }
        const r = e.target.closest("[data-go]"); if (r) go(r.dataset.go);
      });
    }
    if (!refresh && typeof closeSide === "function") { closeSide(); if (typeof side === "function") side(); }
    const all = [...C.threads.values()].filter(t => AN().visible(t.by)).sort((a, b) => (b.updated || "").localeCompare(a.updated || ""));
    const people = new Map(); all.forEach(t => people.set(AN().who(t.by), t.by));
    const pick = all.filter(t => (C.filter === "open" ? !t.resolved : !!t.resolved) && (!C.person || AN().who(t.by) === C.person));
    const nOpen = all.filter(t => !t.resolved).length, nDone = all.length - nOpen;
    el.innerHTML = `<div class="cm-lh"><b>${esc(T("Annotations"))}</b><span class="cm-sp"></span>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Close"))}" data-cm="closelist"></hy-icon-button></div>`
      + `<div class="cm-tabs"><button data-cf="open" aria-pressed="${C.filter === "open"}">${esc(T("comments::Open"))} ${nOpen}</button>`
      + `<button data-cf="done" aria-pressed="${C.filter === "done"}">${esc(T("comments::Resolved"))} ${nDone}</button></div>`
      + (people.size > 1 ? `<div class="cm-ppl">${[...people].map(([k, b]) => `<button data-cp="${esc(k)}" aria-pressed="${C.person === k}"`
        + ` title="${esc(window.hyWhoText ? hyWhoText({ by: b }) : "")}">${face(b, 24)}</button>`).join("")}</div>` : "")
      + (pick.length ? pick.map(t => { const last = t.messages[t.messages.length - 1];
        return `<button class="cm-row" data-go="${esc(t.id)}">${face(t.by, 24)}<span class="cm-rb"><span class="cm-rh"><b>${esc(window.hyWhoText ? hyWhoText(t) : "")}</b>`
          + `<time>${esc(ago(last.created))}</time></span>${t.area && t.anchor ? `<span class="cm-ra">${esc(T("Area"))} ${pctR(t.area)}</span>` : ""}`
          + `${t.anchor && !board.items[t.anchor.obj] ? `<span class="cm-ra">${esc(T("object gone"))}</span>` : ""}<span class="cm-rt">${esc(t.messages[0].text)}</span>`
          + `${t.messages.length > 1 ? `<span class="cm-rr">${esc(T("{n} replies", { n: t.messages.length - 1 }))}</span>` : ""}</span></button>`; }).join("")
        : `<div class="none">${esc(C.filter === "open" ? T("No open annotations on this page") : T("No resolved annotations"))}</div>`);
    el.classList.add("open");
  }
  function go(id) {   // the camera to the pin, the thread open beside it
    const t = C.threads.get(id); if (!t) return;
    const p = where(t); if (!p) return;
    const r = stage.getBoundingClientRect();
    cam.x = p.x - (r.width / 2 - 120) / cam.z; cam.y = p.y - r.height / 2 / cam.z; if (typeof saveCam === "function") saveCam(); render();
    thread(id);
  }

  // Move to page takes the annotations of what goes (P4 B-32): a thread on a moved thing is written on the other page with the thing's
  // id there and taken off this one, the same for ⌘Z of the move; map: the thing's id here -> there. Returns how many went
  async function carry(from, to, map) {
    let n = 0;
    try {
      const d = await AN().api("/api/comments?name=" + encodeURIComponent(from));
      for (const t of d.items || []) {
        const o = t.anchor && t.anchor.obj; if (!o || !(o in map)) continue;
        const c = clone(t); c.anchor = { ...c.anchor, obj: map[o] };
        await AN().api("/api/comments", { name: to, op: "put", id: t.id, thread: c });
        await AN().api("/api/comments", { name: from, op: "put", id: t.id, thread: null }); n++;
      }
    } catch (ex) { AN().fail(ex); }
    if (n) load();
    return n;
  }

  // ---- the bell, the history -------------------------------------------------------------------------------------------------------
  async function fromBell(e) {
    const b = e.target.closest("[data-n]"); if (!b || !b.dataset.n.startsWith("c:")) return;
    e.stopImmediatePropagation();
    const n = (typeof NTF !== "undefined" ? NTF.items : []).find(x => x.id === b.dataset.n); if (!n) return;
    $("#ntf").classList.remove("open"); if (typeof side === "function") side();
    if (n.page && n.page !== BOARD && typeof switchPage === "function") await switchPage(n.page);
    await load(); go(n.thread);
  }
  // history's words: a thread is an Annotation in the interface, a mark of the drawing tools a Drawing (owner 2026-10-09)
  const EV = { comment: "New annotation", reply: "Reply in a thread", "comment-edit": "Annotation changed", "comment-remove": "Annotation deleted",
    resolve: "Annotation resolved", reopen: "Annotation reopened", annotate: "Drawing", "annotate-edit": "Drawing changed", "annotate-remove": "Drawings erased" };
  window.hyEvView = (e, escape) => {
    const k = EV[e.kind]; if (!k) return null;
    const body = e.text ? `<div class="ecm">${escape(e.text)}</div>` : e.count > 1 ? `<div class="em">${escape(T("{n} drawings", { n: e.count }))}</div>` : "";
    return [T(k), body];
  };

  function init() {
    if (!ok() || !stage || !document.getElementById("world")) return void setTimeout(init, 100);
    AN().register("comment", tool);   // a press with a thread open closes it, a click pins, a drag draws an area
    document.addEventListener("pointerover", e => {   // a pin or a list row pointed at lights its area
      const x = e.target.closest && e.target.closest("#cmpins .cmpin, #cmlist [data-go]"); hover(x ? x.dataset.c || x.dataset.go : null);
    });
    const ntf = $("#ntf"); if (ntf) ntf.addEventListener("click", fromBell, true);
    addEventListener("pointerdown", e => {   // a press outside the open thread closes it (an unsent draft goes too); the list too, as the side panels
      const ls = document.getElementById("cmlist");
      if (ls && ls.classList.contains("open") && !ls.contains(e.target) && !(e.target.closest && e.target.closest('[data-ann="list"], .cmpin, #cmthread'))) ls.classList.remove("open");
      const el = document.getElementById("cmthread");
      if (!el || !el.classList.contains("open") || el.contains(e.target) || (e.target.closest && e.target.closest(".cmpin, #cmlist, [data-cm-keep]"))) return;
      const onBoard = e.target === stage || (e.target.closest && e.target.closest("#world, .bgl, #marq, #gsticky"));
      if (AN().active === "comment" && onBoard) return;   // the Annotation tool's own press decides (anncore.js)
      close();
    }, true);
    load(); setInterval(() => { if (!document.hidden && !C.busy) load(); }, 8000);
  }
  const escape = () => { if (AT.list.length) { mentionsOff(); return true; } if (C.open || C.draft) { close(); return true; } return false; };
  window.hyComments = { draw, follow, list, open: thread, close, cancelDraft, load, escape, newAt, light, carry, position: f => { PLACE.push(f); draw(); },
    bounds: f => { C.bounds = typeof f === "function" ? f : null; follow(); },   // a Studio's free part for the open thread (null: the stage)
    threads: () => [...C.threads.values()],
    openCount: () => [...C.threads.values()].filter(t => !t.resolved).length, authors: () => [...C.threads.values()].map(t => t.by).filter(Boolean), get state() { return C; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
