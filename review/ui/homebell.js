// Home's news (owner 2026-10-08: «Я хочу на главной странице по левую сторону видеть не только сколько у меня досок, но и сколько
// обновлений. И еще, может, стоит добавить вверху справа, где настройки, тоже нотификации, чтобы я мог видеть: так, у меня тут что-то
// новенькое появилось»). A classic script (Home loads no modules); its look is ui/homebell.css, the list's and the rows' ui/bell.css.
//   hyHomeBell.count(ps)    the small red count of the news on these boards (each board's news.n, the number on its card), "" at 0: the
//                           sidebar's projects, «No project», a favourite board, «All boards»
//   hyHomeBell.text(nw)     a board's news in one line, the card's tooltip: «12 new: +24 images, 2 notes on Renderings · Codex»
//   hyHomeBell.paint(data)  home.html render(): «All boards»' count, the bell's dot, the open list drawn again, and the faces of who
//                           did the news fitted to the card's line: the data comes first («Мне главное данные»), a face that leaves
//                           the time, frames or size cut short is left out, the first always stays (its tooltip names them all)
// The bell (#hbell, beside the settings, the registry's notifications glyph whose dot turns red while something came since the list was
// last opened) opens #ntf, the board's list with the board's rows (ui/bellrow.js): every board on this Mac with something new, the newest
// first, under its name and its count of news (the card's number). A board's rows are
//   bell   its own bell (GET /api/notifications: title, who, words, pictures) for a board whose server runs. Home is a file page and a
//          board's server answers only its own origin, so the app brings them: Home asks {action: "homeBell"}, the app answers
//          hyimgHomeBell({boards: [{id, base: "http://127.0.0.1:<port>", items, unread}]})   (native/MacNotifications.swift homeBell)
//   news   what Home has for every board, running or not: its news {n, t, rows} (native BoardNews reads the event logs), a row per page
//          and author: «+24 images, 2 notes on Renderings», who with his face; no pictures, no objects. A running board shows them
//          too, but for those its bell already tells: a bell row of the same page, agent and person, from the news' time on (the
//          app's since, else a day before the newest), an agent's row for all he did there, a comment's for the comments. So the
//          card's count stays what the rows say, and «Put 24 renderings» does not come twice as «+24 images»
// A click opens the board at the row's place: {action: "open", id, page, obj, area} (native: App.homeOpen goes there as a banner's click
// does). Opening the list reads it: the dot goes, the rows newer than the last look stay tinted while it is open, and the bell rows are
// read on their boards: {action: "bellRead", read: {board id: [row ids]}} (native: App.homeBellRead).
(() => {
  if (window.hyHomeBell) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const toApp = m => { try { webkit.messageHandlers.hyimg.postMessage(m); } catch { console.log("no native bridge", m.action); } };
  const store = { get(k) { try { return +localStorage.getItem(k) || 0; } catch { return 0; } }, set(k, v) { try { localStorage.setItem(k, String(v)); } catch {} } };
  const SEEN_KEY = "home.bell.seen", PER_BOARD = 6, ASK_MS = 20000, DAY = 86400;
  const BELL = new Map();   // board id -> {base, items}: the bell rows the app brought (boards whose server runs)
  const READ = new Set();   // the bell rows Home has shown and sent read: unread still in an answer that crossed the read on its way
  let DATA = null, SEEN = store.get(SEEN_KEY), FRESH = new Set(), asked = 0;
  const now = () => Date.now() / 1000;
  const newsN = p => (p && p.news && p.news.n) || 0;
  const badge = n => n ? `<span class="nb hb-n" title="${esc(T("{n} new", { n }))}">${n > 99 ? "99+" : n}</span>` : "";

  // a board's news in words: by page (the first three) and kind, then who («Codex (Name)» for another person's agent, ui/people.js) ----
  function tally(rows, key) {
    const out = new Map();
    (rows || []).forEach(r => {
      const k = key(r); if (!out.has(k)) out.set(k, { page: r.p || T("Page 1"), pid: r.pid || "", r, add: 0, rm: 0, groups: 0, notes: 0, heads: 0, moves: 0, cms: 0, draws: 0, other: 0 });
      const c = out.get(k), x = r.k;
      if (x === "add") c.add += r.c; else if (x === "group") { c.groups += r.n; c.add += r.c; } else if (x === "remove") c.rm += r.c;
      else if (x === "note" || x === "note-edit") c.notes += r.n; else if (x === "text" || x === "text-edit") c.heads += r.n;
      else if (x === "comment" || x === "reply") c.cms += r.n; else if (x === "annotate") c.draws += r.n; else if (x === "move") c.moves += r.n; else c.other += r.n;
    });
    return out;
  }
  const what = c => [c.add && T("+{n} images", { n: c.add }), c.rm && T("−{n} images", { n: c.rm }), c.groups && T("{n} groups", { n: c.groups }),
    c.notes && T("{n} notes", { n: c.notes }), c.heads && T("{n} headings", { n: c.heads }), c.moves && T("{n} moves", { n: c.moves }),
    c.cms && T("{n} comments", { n: c.cms }), c.draws && T("{n} drawings", { n: c.draws }), c.other && T("{n} other changes", { n: c.other })].filter(Boolean).join(", ");
  function text(nw) {
    const pages = tally(nw.rows, r => r.p || T("Page 1")), who = [];
    (nw.rows || []).forEach(r => { const w = window.hyPeople ? hyPeople.newsWho(r) : r.w; if (w && !who.includes(w)) who.push(w); });
    const parts = [...pages.values()].slice(0, 3).map(c => { const w = what(c); return w && T("{what} on {page}", { what: w, page: c.page }); }).filter(Boolean);
    if (pages.size > 3) parts.push(T("{n} more pages", { n: pages.size - 3 }));
    // Russian names the page first («Renderings: +24 картинки»: a page's name stays as it is written), its head ends in «·», not «:»
    return (parts.length ? T("{n} new: {list}", { n: nw.n, list: parts.join("; ") }) : T("{n} new", { n: nw.n })) + (who.length ? " · " + who.join(", ") : "");
  }

  // the rows of one board in the list ---------------------------------------------------------------------------------------------
  const me = () => ((window.hyPeople && hyPeople.me()) || {}).id || "";
  const newsT = p => (p.news && (p.news.t || p.updated)) || 0;
  const bellOf = p => { const b = BELL.get(p.id); return b && b.items.length ? b : null; };
  const lastOf = p => Math.max(newsN(p) ? newsT(p) : 0, ...(bellOf(p) ? bellOf(p).items.map(i => +i.ts || 0) : [0]));
  // a news row as a bell row: who by his face (the agent's badge on it), what by page, the board's newest time; kind: the agent's kind
  // ("" for a person's own edits), talk: comments and nothing else
  const ag = v => (window.HY_AGENTS ? HY_AGENTS.kind(v) : v && v !== "app" && v !== "owner" ? "agent" : "");
  function newsRows(p) {
    return [...tally(p.news.rows, r => `${r.pid || r.p}\u0001${r.w}\u0001${r.u || ""}`).values()].map((c, i) => {
      const w = what(c), kind = c.r.w === "ai" ? "agent" : c.r.w === "owner" ? "" : ag(c.r.w);
      return { id: `news:${i}`, title: w ? T("{what} on {page}", { what: w, page: c.page }) : c.page, who: c.r.w, page: c.pid, news: true,
        by: { person: c.r.u || me(), via: kind || "app" }, t: newsT(p), kind,
        talk: c.cms > 0 && !(c.add || c.rm || c.groups || c.notes || c.heads || c.moves || c.draws || c.other) };
    });
  }
  // a bell row tells a news row: the same page, agent and person; an agent's row all he did there, a comment's only comments
  const low = s => String(s || "").toLowerCase();
  function tells(i, n) {
    const by = i.by || {}, kind = ag(by.via) || (i.type === "agent" ? ag(i.who) : "");
    if ((i.page || "main") !== (n.page || "main") || kind !== n.kind || low(by.person || me()) !== low(n.by.person)) return false;
    return i.type === "agent" || n.talk;
  }
  const rowKey = (p, n) => `${p.id}\u0001${n.id}`;
  const at = n => (n.news ? n.t : +n.ts || 0);
  // a board's rows: its bell's and the news it does not tell, the newest first (the news at the board's newest time); told: the bell
  // rows that carry some of the news (tinted with it)
  function listOf(p) {
    const b = bellOf(p), news = newsN(p) ? newsRows(p) : [], told = new Set();
    if (!b) return { list: news, told };
    const from = (+p.news?.since || newsT(p) - DAY) - 1;   // a bell row before the news began is about older work
    const left = news.filter(n => { const i = b.items.find(i => (+i.ts || 0) >= from && tells(i, n)); if (i) told.add(String(i.id)); return !i; });
    return { list: [...b.items, ...left].sort((x, y) => at(y) - at(x)), told };
  }
  const rows = p => listOf(p).list;
  function draw() {
    const el = document.getElementById("ntf"); if (!el || !el.classList.contains("open")) return;
    const boards = ((DATA && DATA.projects) || []).filter(p => rows(p).length).sort((a, b) => lastOf(b) - lastOf(a));
    const h = window.hyBellHead() + (boards.length ? boards.map(p => {
      const L = rows(p), b = bellOf(p), shown = L.slice(0, PER_BOARD), more = L.length - shown.length;
      return `<div class="hb-b" data-hb-board="${esc(p.id)}"><button type="button" class="hb-h" data-hb-open="${esc(p.id)}" title="${esc(T("Open {name}", { name: p.name }))}">`
        + `${window.hyIcon ? hyIcon("board", 14, 1.8) : ""}<span class="hb-bn">${esc(p.name)}</span>${badge(newsN(p))}</button>`
        + shown.map(n => window.hyBellRow(n, { base: b ? b.base : "", attrs: ` data-hb="${esc(p.id)}"`, read: !FRESH.has(rowKey(p, n)),
          when: n.news ? (window.hyBellAgo ? hyBellAgo(n.t) : "") : "" })).join("")
        + (more > 0 ? `<button type="button" class="hb-more" data-hb-open="${esc(p.id)}">${esc(T("{n} more", { n: more }))}</button>` : "") + "</div>";
    }).join("") : `<div class="none">${esc(T("Nothing new on the boards"))}</div>`);
    if (el._h !== h) el.innerHTML = el._h = h;
  }

  // the dot: something came since the list was last opened (a board's news), or a running board's bell has a row nobody read ------
  const unread = (p, i) => !i.read && !READ.has(rowKey(p, i));
  const fresh = p => (newsN(p) && newsT(p) > SEEN) || (bellOf(p) && bellOf(p).items.some(i => unread(p, i)));
  function dot() {
    const b = document.getElementById("hbell"); if (!b) return;
    b.classList.toggle("dot", ((DATA && DATA.projects) || []).some(fresh));
  }
  function ask() { asked = Date.now(); toApp({ action: "homeBell" }); }
  // what is new for this look: tinted while the list is open; the bell rows are read on their boards
  function look(markNews) {
    const read = {};
    ((DATA && DATA.projects) || []).forEach(p => {
      const b = bellOf(p);
      if (b) b.items.forEach(i => { if (unread(p, i)) { FRESH.add(rowKey(p, i)); READ.add(rowKey(p, i)); (read[p.id] = read[p.id] || []).push(i.id); } });
      // news since the last look: its rows, and the bell rows that tell it
      if (markNews && newsN(p) && newsT(p) > SEEN) { const { list, told } = listOf(p); list.forEach(n => { if (n.news || told.has(String(n.id))) FRESH.add(rowKey(p, n)); }); }
    });
    if (Object.keys(read).length) toApp({ action: "bellRead", read });
  }
  function open(on) {
    const el = document.getElementById("ntf"), b = document.getElementById("hbell"); if (!el || !b) return;
    if (on === el.classList.contains("open")) return;
    el.classList.toggle("open", on); b.setAttribute("aria-expanded", String(on));
    const btn = b.querySelector("button"); if (btn) btn.setAttribute("aria-expanded", String(on));
    if (!on) { FRESH = new Set(); return; }
    look(true); SEEN = now(); store.set(SEEN_KEY, SEEN); dot(); draw(); ask();
  }
  function go(id, more) {
    open(false);
    if (typeof window.openProject === "function") window.openProject(id, more); else toApp({ action: "open", id, ...more });
  }

  // the bell and its list, before the settings button, once the page is there ------------------------------------------------------
  function mount() {
    if (document.getElementById("hbell")) return;
    const l = esc(T("Notifications")), set = document.getElementById("bset");
    const b = document.createElement("hy-icon-button");
    b.id = "hbell"; b.className = "hy-bell"; b.setAttribute("size", "plate"); b.setAttribute("label", T("Notifications"));
    b.setAttribute("aria-expanded", "false");
    b.innerHTML = `<button type="button" aria-label="${l}" title="${l}" aria-haspopup="dialog" aria-expanded="false" aria-controls="ntf">`
      + `${window.hyIcon ? hyIcon("notifications", 18, 1.8) : ""}</button>`;
    const el = document.createElement("div"); el.id = "ntf"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", T("Notifications"));
    if (set) set.before(b, el); else document.body.append(b, el);
    b.addEventListener("click", e => { e.stopPropagation(); open(!el.classList.contains("open")); });
    el.addEventListener("click", e => {
      e.stopPropagation();
      const o = e.target.closest("[data-hb-open]"); if (o) { go(o.dataset.hbOpen); return; }
      const r = e.target.closest(".nt[data-hb]"); if (!r) return;
      const p = ((DATA && DATA.projects) || []).find(x => x.id === r.dataset.hb), n = p && rows(p).find(x => String(x.id) === r.dataset.n);
      if (!p || !n) return;
      const more = {}; if (n.page) more.page = n.page; if ((n.ids || []).length) more.obj = n.ids;
      if (n.area && !(n.ids || []).length) more.area = [n.area.x, n.area.y, n.area.w, n.area.h];
      go(p.id, more);
    });
    document.addEventListener("pointerdown", e => { if (!e.target.closest("#ntf, #hbell")) open(false); }, true);
    document.addEventListener("keydown", e => { if (e.key === "Escape" && el.classList.contains("open")) { open(false); b.querySelector("button").focus(); } });
    dot();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();

  // the faces before a board's news count, the last ones out while the line's data ends in … (a card's line, the list's time)
  function fit() {
    document.querySelectorAll(".meta .s, .list .card .c3").forEach(line => {
      const words = line.querySelector(":scope > span"), faces = [...line.querySelectorAll(":scope > .nb-who > hy-avatar")];
      if (!words || faces.length < 2) return;
      faces.forEach(f => { f.hidden = false; });
      for (let k = faces.length - 1; k > 0 && words.scrollWidth > words.clientWidth + .5; k--) faces[k].hidden = true;
    });
  }
  addEventListener("resize", () => { cancelAnimationFrame(fit.t); fit.t = requestAnimationFrame(fit); });
  if (document.fonts) document.fonts.ready.then(fit);
  function paint(data) {
    DATA = data; cancelAnimationFrame(fit.t); fit.t = requestAnimationFrame(fit);   // after render() has drawn the cards
    const all = (data && data.projects) || [], a = document.querySelector("aside [data-tab=all]");
    if (a) { const old = a.querySelector(".hb-n"), h = badge(all.reduce((s, p) => s + newsN(p), 0)); if (old) old.remove(); if (h) a.insertAdjacentHTML("beforeend", h); }
    dot(); draw();
    if (Date.now() - asked > ASK_MS) ask();
  }
  // the app's answer to homeBell: the bell rows of the boards whose server runs; a board not named has none (stopped)
  window.hyimgHomeBell = d => {
    BELL.clear();
    ((d && d.boards) || []).forEach(x => {
      if (!x || !x.id || !Array.isArray(x.items)) return;
      BELL.set(String(x.id), { base: /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(x.base || "") ? x.base : "", items: x.items.filter(i => i && i.id) });
    });
    if (document.getElementById("ntf") && document.getElementById("ntf").classList.contains("open")) look(false);
    dot(); draw();
    return true;
  };
  window.hyHomeBell = { count: ps => badge((ps || []).reduce((s, p) => s + newsN(p), 0)), text, paint, open };
})();
