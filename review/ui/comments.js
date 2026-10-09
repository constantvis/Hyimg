// Comments on the board, as in Figma (owner 2026-10-07: «добавлять комменты, как в Figma ... возможность тегать участников»). A click
// with the Comment tool (C in Annotate, ⇧C on the board) on an object or on empty canvas drops a pin with a thread: text with
// @mentions (people this Mac knows, «@Claude» = your own Claude, «@Codex · Name» another person's agent), replies, edit and delete of
// your own, Resolve and Reopen, and the list of the page's comments (open or resolved, by person, a click goes to the pin). A pin wears
// its author's face, an agent's comment the agent's badge on its person's face. A pin on an object moves with it (ui/annotate.js
// anchorAt). Each action is one undo step. The bell names others' comments and every mention of you or your agents (review/comments.py).
(() => {
  if (window.hyComments) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)));
  const $ = q => document.querySelector(q);
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const C = { threads: new Map(), page: null, open: null, draft: null, filter: "open", person: "", busy: false, lit: new Set() };
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
      C.threads = new Map((d.items || []).map(t => [t.id, t])); C.page = page; draw(); changed(); if (C.open && !C.draft) thread(C.open);
      if ($("#cmlist.open")) list(true);
      AN().paintBar();
    } catch {}
  }
  async function send(body) {
    const d = await AN().api("/api/comments", { name: BOARD, ...body });
    if (d.thread && !d.deleted) C.threads.set(d.thread.id, d.thread);
    if (d.deleted) { C.threads.delete(d.deleted); if (C.open === d.deleted) close(); }
    draw(); changed(); if (C.open && C.threads.has(C.open)) thread(C.open); if ($("#cmlist.open")) list(true); AN().paintBar();
    return d;
  }
  // one undo step: the thread as it was before, as it is after (null: none); undo and redo send it back whole (op put), refused when
  // someone changed it since (base: the updated the server must still have)
  function stepOf(before, after) {
    let last = after ? after.updated : null;
    const go = async t => { const d = await send({ op: "put", id: (before || after).id, thread: t, base: last }); last = d.thread && !d.deleted ? d.thread.updated : null; };
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
      want.set(t.id, [p, `${face(t.by, 24)}${n ? `<b class="cmp-n">${n}</b>` : ""}`, `${window.hyWhoText ? hyWhoText(t) : ""}: ${t.messages[0].text.slice(0, 80)}${off}`]);
    }
    if (C.draft) want.set("draft", [C.draft.pos, face(AN().state.me(), 24), T("New comment")]);
    drawAreas(el);
    for (const p of [...el.querySelectorAll(":scope > .cmpin")]) if (!want.has(p.dataset.c)) p.remove();
    for (const [id, [p, h, title]] of want) {
      let b = el.querySelector(`:scope > [data-c="${id}"]`);
      if (!b) { b = document.createElement("button"); b.className = "cmpin"; b.dataset.c = id; el.appendChild(b); }
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
      el.addEventListener("click", click); el.addEventListener("keydown", key); el.addEventListener("input", typed);
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
    const keep = C.open === id ? (pop().querySelector("textarea") || {}).value || "" : "";
    const fresh = C.open !== id;
    C.open = id; C.ment = C.open === id ? C.ment || [] : [];
    const el = pop(), what = t.element ? t.element.css || t.element.tag || "" : t.anchor ? (window.hyNoteLink && board.items[t.anchor.obj]
      ? hyNoteLink.label(board, t.anchor.obj) : t.anchor.file || "") : "";
    el.innerHTML = `<div class="cm-h"><b>${esc(T("Comment"))}</b>${what ? `<span class="cm-w" title="${esc(what)}">· ${esc(what.split("/").pop())}</span>` : ""}`
      + `<span class="cm-sp"></span><hy-icon-button icon="${t.resolved ? "reset" : "resolve"}" size="s" label="${esc(t.resolved ? T("Reopen") : T("Resolve"))}"`
      + ` data-cm="${t.resolved ? "reopen" : "resolve"}"${t.resolved ? "" : ' class="cm-rs"'}></hy-icon-button>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Close"))} · Esc" data-cm="close"></hy-icon-button></div>`
      + (t.resolved ? `<div class="hy-hint cm-rd">${T("Resolved by <b>{who}</b>", { who: esc(window.hyWhoText ? hyWhoText(t.resolved) : "") })}</div>` : "")
      + `<div class="cm-msgs">${t.messages.map(msg).join("")}</div>` + composer(T("Reply…"));
    el.classList.add("open"); el.dataset.c = id;
    const ta = el.querySelector("textarea"); ta.value = keep; grow(ta);
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
    C.ment = [];
    const el = pop();
    const what = C.draft.element ? C.draft.element.css || C.draft.element.tag || "" : "";
    el.innerHTML = `<div class="cm-h"><b>${esc(T("New comment"))}</b>${what ? `<span class="cm-w" title="${esc(what)}">· ${esc(what)}</span>` : ""}<span class="cm-sp"></span>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Cancel"))} · Esc" data-cm="close"></hy-icon-button></div>`
      + composer(C.draft.area ? T("Comment on area {n}", { n: areaN(C.draft.anchor) }) : T("Add a comment… @ to mention"));
    el.classList.add("open"); el.dataset.c = "draft";
    follow(); draw(); el.querySelector("textarea").focus(); setTimeout(() => { const ta = el.querySelector("textarea"); if (ta && document.activeElement !== ta) ta.focus(); }, 0);
  }
  const areaN = an => 1 + [...C.threads.values()].filter(t => t.area && (an ? t.anchor && t.anchor.obj === an.obj : !t.anchor)).length;
  function close() {
    const el = document.getElementById("cmthread"); if (el) { el.classList.remove("open"); el.innerHTML = ""; }
    const dr = C.draft; C.open = null; C.draft = null; mentionsOff(); draw();
    unsent(dr);
  }
  function unsent(dr) { if (dr && dr.cancel) try { dr.cancel(); } catch (ex) { console.error("comment cancel", ex); } }
  function cancelDraft() { if (C.draft) close(); }
  function follow() {   // the open thread stands beside its pin, wherever the camera goes
    const el = document.getElementById("cmthread"); if (!el || !el.classList.contains("open") || typeof cam === "undefined") return;
    const t = C.threads.get(C.open), p = C.draft ? C.draft.pos : t && where(t); if (!p) return;
    const r = stage.getBoundingClientRect(), x = (p.x - cam.x) * cam.z, y = (p.y - cam.y) * cam.z, w = el.offsetWidth, h = el.offsetHeight;
    let left = x + 40, top = y - 40;
    if (left + w > r.width - 12) left = x - w - 16;
    el.style.left = Math.max(12, Math.min(r.width - w - 12, left)) + "px"; el.style.top = Math.max(58, Math.min(r.height - h - 12, top)) + "px";
  }
  async function submit() {
    const el = pop(), ta = el.querySelector("textarea"), v = (ta && ta.value || "").trim(); if (!v || C.busy) return;
    const ment = (C.ment || []).filter(m => v.includes("@" + m.label));
    C.busy = true;
    try {
      if (C.draft) {
        const d = C.draft; C.draft = null;
        const res = await act({ op: "new", anchor: d.anchor, at: d.at, element: d.element, area: d.area, text: v, mentions: ment });
        if (res && res.thread) { C.made = res.thread.id; thread(res.thread.id); C.made = null; const ta = pop().querySelector("textarea"); if (ta) ta.focus(); }
        else { close(); unsent(d); }
      } else if (C.open) {
        const before = clone(C.threads.get(C.open));
        if (C.edit) { const mid = C.edit; C.edit = null; await act({ op: "edit", id: C.open, mid, text: v, mentions: ment }, before); }
        else { ta.value = ""; await act({ op: "reply", id: C.open, text: v, mentions: ment }, before); }
        if (C.open) { thread(C.open); const t2 = pop().querySelector("textarea"); if (t2) t2.focus(); }
      }
    } finally { C.busy = false; C.ment = []; }
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
      C.edit = x.id; C.ment = (x.mentions || []).map(q => ({ ...q })); ta.value = x.text; ta.placeholder = T("Edit the comment…"); grow(ta); ta.focus();
    }
  }
  function key(e) {
    e.stopPropagation();
    if (AT.list.length && ["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(e.key)) {
      e.preventDefault();
      if (e.key === "Escape") { mentionsOff(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { AT.i = (AT.i + (e.key === "ArrowDown" ? 1 : -1) + AT.list.length) % AT.list.length; paintAt(); return; }
      pickMention(AT.i); return;
    }
    if (e.key === "Enter" && !e.shiftKey && e.target.matches("textarea")) { e.preventDefault(); submit(); return; }
    if (e.key === "Escape") { e.preventDefault(); if (C.edit) { C.edit = null; thread(C.open); return; } close(); }
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
      el = document.createElement("div"); el.id = "cmlist"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", T("Comments")); stage.appendChild(el);
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
    el.innerHTML = `<div class="cm-lh"><b>${esc(T("Comments"))}</b><span class="cm-sp"></span>`
      + `<hy-icon-button icon="close" size="s" label="${esc(T("Close"))}" data-cm="closelist"></hy-icon-button></div>`
      + `<div class="cm-tabs"><button data-cf="open" aria-pressed="${C.filter === "open"}">${esc(T("comments::Open"))} ${nOpen}</button>`
      + `<button data-cf="done" aria-pressed="${C.filter === "done"}">${esc(T("comments::Resolved"))} ${nDone}</button></div>`
      + (people.size > 1 ? `<div class="cm-ppl">${[...people].map(([k, b]) => `<button data-cp="${esc(k)}" aria-pressed="${C.person === k}"`
        + ` title="${esc(window.hyWhoText ? hyWhoText({ by: b }) : "")}">${face(b, 24)}</button>`).join("")}</div>` : "")
      + (pick.length ? pick.map(t => { const last = t.messages[t.messages.length - 1];
        return `<button class="cm-row" data-go="${esc(t.id)}">${face(t.by, 24)}<span class="cm-rb"><span class="cm-rh"><b>${esc(window.hyWhoText ? hyWhoText(t) : "")}</b>`
          + `<time>${esc(ago(last.created))}</time></span>${t.area && t.anchor ? `<span class="cm-ra">${esc(T("Area"))} ${pctR(t.area)}</span>` : ""}`
          + `<span class="cm-rt">${esc(t.messages[0].text)}</span>`
          + `${t.messages.length > 1 ? `<span class="cm-rr">${esc(T("{n} replies", { n: t.messages.length - 1 }))}</span>` : ""}</span></button>`; }).join("")
        : `<div class="none">${esc(C.filter === "open" ? T("No open comments on this page") : T("No resolved comments"))}</div>`);
    el.classList.add("open");
  }
  function go(id) {   // the camera to the pin, the thread open beside it
    const t = C.threads.get(id); if (!t) return;
    const p = where(t); if (!p) return;
    const r = stage.getBoundingClientRect();
    cam.x = p.x - (r.width / 2 - 120) / cam.z; cam.y = p.y - r.height / 2 / cam.z; if (typeof saveCam === "function") saveCam(); render();
    thread(id);
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
  const EV = { comment: "New comment", reply: "Reply in a thread", "comment-edit": "Comment changed", "comment-remove": "Comment deleted", resolve: "Comment resolved",
    reopen: "Comment reopened", annotate: "Annotation", "annotate-edit": "Annotation changed", "annotate-remove": "Annotations erased" };
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
      if (AN().active === "comment" && onBoard) return;   // the Comment tool's own press decides (annotate.js)
      close();
    }, true);
    load(); setInterval(() => { if (!document.hidden && !C.busy) load(); }, 8000);
  }
  const escape = () => { if (AT.list.length) { mentionsOff(); return true; } if (C.open || C.draft) { close(); return true; } return false; };
  window.hyComments = { draw, follow, list, open: thread, close, cancelDraft, load, escape, newAt, light, position: f => { PLACE.push(f); draw(); },
    threads: () => [...C.threads.values()],
    openCount: () => [...C.threads.values()].filter(t => !t.resolved).length, authors: () => [...C.threads.values()].map(t => t.by).filter(Boolean), get state() { return C; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
