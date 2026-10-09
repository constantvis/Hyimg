// Home's standard Archive (owner 2026-10-08: «Папку архив (или проект) Архив сделай, пожалуйста, стандартный, ее не удалить, она просто
// есть. И туда будем пихать все, что не должно светиться нигде. Там просто будут лежать архивные какие-то старые файлы»). A classic script
// (Home loads no modules); its look is ui/homearchive.css, the app's side (⌃Tab, macOS notifications, starting servers) native/HomeArchive.swift.
// The Archive is a project of home.json like the owner's own, folders[] with the id "archive", so the board's crumb and Home's loading
// plate show it as any project. A board made while the Archive is open goes into no project: a new board is in use, not put away.
// Its own fields:
//   name     «Archive» | «Архив», written again in the app's language (the board's crumb reads the name from the file)
//   icon     "archive", the registry's box (ui/icons.js; ui/projicon.js draws it, a project can't pick it)
//   from     {board id: the project it left for the Archive, "" for none}: «Restore» takes the board back there
//   merged   the owner's own archive projects folded into it once, as they were (name, icon, colour, boards), so the fold can be undone
// It always exists: ensure() makes it when home.json has none and keeps it last of the projects (Home writes that at once only over a
// home.json the app could read; the app keeps the file's Archive when something writes home.json without it, HomeArchive.swift kept).
// It has no menu of its own (a right click gives the empty space's), a double click does not rename it, its icon opens no picker. Its
// row stands after «No project», at the bottom of Projects: «No project» holds boards still in use, the Archive the ones out of use, so
// the list goes from live to put away, as Mail keeps Archive under the mailboxes. A board in it shows only there: not in Recent, All
// boards, Favorites, the news counts, the bell or «Only new», and Home never starts its server (no key on its card, no «Start server»;
// the app refuses too). Moving an open board in stops its server. A search of Recent or All boards lists the Archive's matches under the
// results as «In Archive», dimmed: out of sight, not lost; Home's filters hold there too, so with «Only new» on (an archived board has
// no news on Home) none are listed. Opening an archived board works as for any board.
//   hyArchive.ensure(HOME)               the Archive there and in shape; true when HOME changed and should be saved
//   hyArchive.has(id), is(f)             a board in the Archive (as of the last ensure); a project (or its id) that is the Archive
//   hyArchive.mine(HOME), add(HOME, f)   the owner's projects without the Archive; a new project put before it
//   hyArchive.live(data)                 the app's list without the archived boards (the bell, «All boards»' count)
//   hyArchive.moving(HOME, data, id, to) moveTo's first step: where a board came from, the server of one going in stopped
//   hyArchive.row(HOME, tab)             the sidebar's row
//   hyArchive.menu(HOME, id)             a board's menu item: «Move to Archive», or «Restore» with where it goes
//   hyArchive.cls(id), tag(id)           a card's class; its «Archived» label on the cover (a list row has its project's column)
//   hyArchive.found(all, tab, q, asList) «In Archive» under a search of Recent or All boards, as home.html's cards or rows; all is
//                                        the app's boards after Home's filters (home.html shown), this keeps the archived matches
//   hyArchive.empty()                    the Archive with nothing in it
(() => {
  if (window.hyArchive) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const toApp = m => { try { webkit.messageHandlers.hyimg.postMessage(m); } catch { console.log("no native bridge", m.action); } };
  const ID = "archive";
  // the owner's own archive, made by hand before this one existed («_Archive», «Архив»): folded in once, when the Archive is made
  const OWN = /^[\s_.\-·]*(archives?|archived|архивы?)[\s_.\-·]*$/i;
  let SET = new Set();

  const of = HOME => (HOME.folders || []).find(f => f.id === ID);
  const is = f => (typeof f === "string" ? f : f && f.id) === ID;
  function ensure(HOME) {
    let changed = false;
    if (!Array.isArray(HOME.folders)) HOME.folders = [];
    let a = of(HOME);
    if (!a) {
      a = { id: ID, name: T("Archive"), icon: ID, projects: [], from: {} };
      const own = HOME.folders.filter(f => OWN.test(String(f.name || "")));
      own.forEach(f => {
        (a.merged = a.merged || []).push({ id: f.id, name: f.name, icon: f.icon || "", color: f.color || "", projects: [...(f.projects || [])] });
        (f.projects || []).forEach(id => { if (!a.projects.includes(id)) { a.projects.push(id); a.from[id] = ""; } });
      });
      // a board is in one project: what went into the Archive leaves the others
      HOME.folders = HOME.folders.filter(f => !own.includes(f)).map(f => ({ ...f, projects: (f.projects || []).filter(id => !a.projects.includes(id)) }));
      HOME.folders.push(a); changed = true;
    }
    if (HOME.folders[HOME.folders.length - 1] !== a) { HOME.folders = [...HOME.folders.filter(f => f !== a), a]; changed = true; }
    if (a.name !== T("Archive")) { a.name = T("Archive"); changed = true; }
    if (a.icon !== ID) { a.icon = ID; changed = true; }
    if (a.color) { delete a.color; changed = true; }
    a.projects = Array.isArray(a.projects) ? a.projects : [];
    const from = a.from && typeof a.from === "object" ? a.from : {}, keep = {};
    Object.keys(from).forEach(id => { if (a.projects.includes(id)) keep[id] = String(from[id] || ""); else changed = true; });
    a.from = keep;
    SET = new Set(a.projects);
    return changed;
  }
  const has = id => SET.has(id);
  const mine = HOME => (HOME.folders || []).filter(f => !is(f));
  function add(HOME, f) {
    const k = HOME.folders.findIndex(is);
    if (k < 0) HOME.folders.push(f); else HOME.folders.splice(k, 0, f);
  }
  const live = data => ({ ...(data || {}), projects: ((data && data.projects) || []).filter(p => !has(p.id)) });
  // where the board came from, before moveTo takes it out of every project; an open board going in is stopped (the app saves it first)
  function moving(HOME, data, id, to) {
    const a = of(HOME); if (!a) return;
    a.from = a.from || {};
    const inside = a.projects.includes(id);
    if (is(to) && !inside) {
      const f = mine(HOME).find(x => (x.projects || []).includes(id));
      a.from[id] = f ? f.id : "";
      const p = ((data && data.projects) || []).find(x => x.id === id);
      if (p && p.open) toApp({ action: "stopServer", id });
    } else if (!is(to)) delete a.from[id];
  }
  // the project «Restore» goes to: the one it came from while it still exists, else none
  const back = (HOME, id) => { const a = of(HOME), f = a && a.from && a.from[id]; return f && mine(HOME).some(x => x.id === f) ? f : ""; };

  const icon = size => `<span class="pji" style="--pj:${size}px" aria-hidden="true">${window.hyIcon ? hyIcon("archive", 0, 1.8) : ""}</span>`;
  function row(HOME, tab) {
    const a = of(HOME), n = a ? a.projects.length : 0, tip = esc(T("Old boards that show nowhere else"));
    return `<button class="nav folder ar-nav" data-folder="${ID}" aria-current="${tab === "f:" + ID}" title="${tip}">${icon(16)}`
      + `<span class="nm">${esc(T("Archive"))}</span><span class="ct">${n}</span></button>`;
  }
  function menu(HOME, id) {
    const item = window.hyMenuItem;
    if (!item) return "";
    if (!has(id)) return item(`data-local="move" data-id="${esc(id)}" data-f="${ID}"`, "archive", esc(T("Move to Archive")));
    const to = back(HOME, id), f = to && mine(HOME).find(x => x.id === to);
    const where = f ? T("to “{name}”", { name: esc(f.name) }) : esc(T("to No project"));
    return item(`data-local="move" data-id="${esc(id)}" data-f="${esc(to)}"`, "unarchive", `${esc(T("Restore"))} <span class="mh">${where}</span>`);
  }
  const cls = id => (has(id) ? " archived" : "");
  const tag = id => (has(id) ? `<span class="ar-chip">${window.hyIcon ? hyIcon("archive", 12, 2) : ""}${esc(T("Archived"))}</span>` : "");
  function found(all, tab, q, asList) {
    q = String(q || "").trim().toLowerCase();
    const draw = asList ? window.rowHtml : window.cardHtml;   // home.html's own, so a found board is the card it is everywhere
    if (!q || (tab !== "recent" && tab !== "all") || typeof draw !== "function") return "";
    const list = (all || []).filter(p => has(p.id) && ((p.name || "").toLowerCase().includes(q) || (p.path || "").toLowerCase().includes(q)));
    if (!list.length) return "";
    return `<section class="ar-found" aria-label="${esc(T("In Archive"))}"><h2>${icon(15)}${esc(T("In Archive"))}<span>${list.length}</span></h2>`
      + `<div class="${asList ? "list" : "grid"}">${list.map(p => draw(p)).join("")}</div></section>`;
  }
  const empty = () => esc(T("Nothing in the Archive"))
    + `<p class="hy-hint">${T("<b>Drag boards here</b> or choose <b>Move to Archive</b> in a board's menu")}</p>`;

  window.hyArchive = { ID, ensure, has, is, mine, add, live, moving, back, row, menu, cls, tag, found, empty };
})();
