// One kind of menu item for the whole app (owner 2026-10-04: «the right-click elements must be standardised everywhere in the app
// in one style»): an icon on the left, the label, the shortcut on the right in key caps like the shortcuts panel (canvas #keys).
// The board's right-click menu, the pages menu, the library's card menu and Home's menus build their items with hyMenuItem;
// the look is in ui/look.css (.ml, .mk).
//   hyMenuItem('data-act="group"', "group", "Сгруппировать", ["⌘", "G"], ' class="danger"')
// the icon is a name from HY_IC, or markup of its own (a project's icon on Home, ui/projicon.js)
(() => {
  // the words in the app's language (ui/i18n.js; its Russian in ui/lang-common.js, owner 2026-10-06); a page without i18n.js: English
  const t = (k, v) => window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  // a menu item's icon is the app's (ui/icons.js hyIcon, owner 2026-10-07: «одно значение, одна иконка»), 15 px in the menus' 1.9 line.
  // The menus' names are the registry's; the few older ones the callers still pass are listed here once, each to its registry name:
  // «Show in Finder» wears a plain folder, not the Finder face (owner 2026-10-06: «иконку нужно взять просто папку, а не finder»)
  const NAME = { del: "trash", dup: "duplicate", file: "doc", finder: "folder", topage: "toPage", copyprops: "copyProps", pasteprops: "pasteProps", clearprops: "clearProps",
    orderfront: "orderFront", orderforward: "orderForward", orderbackward: "orderBackward", orderback: "orderBack" };
  const IC = new Proxy({}, { get: (o, k) => typeof k === "string" && window.hyIcon ? window.hyIcon(NAME[k] || k, 15, 1.9) || undefined : undefined });
  window.HY_IC = IC;
  // the app's marking colours: the board's note colours (canvas.html NCOL), also a folder's colour in the library's tree and a node's in
  // the 3D editor's tree (owner 2026-10-06: «on top we have color change same as for notes»). A menu that colours something starts with
  // hyMenuColors: a row of round swatches, the first one «no colour»; a click on one gives its name in data-color ("" for none)
  const COLORS = { yellow: "#f4c430", orange: "#f59a3d", red: "#ef6a6a", pink: "#f08cc4", purple: "#b79cf2", blue: "#7dbbf5", green: "#7fd49b", grey: "#d9d9de" };
  window.HY_COLORS = COLORS;
  window.hyMenuColors = cur => `<div class="msw" role="group" aria-label="${t("Colour")}">`
    + `<button class="none ${cur ? "" : "on"}" data-color="" title="${t("No colour")}" aria-label="${t("No colour")}"></button>`
    + Object.entries(COLORS).map(([k, v]) => `<button class="${cur === k ? "on" : ""}" data-color="${k}" title="${t(k)}" aria-label="${t(k)}" style="--c:${v}"></button>`).join("")
    + `</div>`;
  // A row's colour in any list (owner 2026-10-07: «в layers при нажатии правой кнопки добавить colors как в notes ... и так в любых: 3D
  // editor, image editor»): the list's right click starts with hyMenuColors(cur); hyColorPick(e) is the colour a click chose ("" for none,
  // null when the click was not on a swatch); the row wears it with the class hy-rc and --hy-rc: hyRowColor(name) (a stripe on its left)
  window.hyColorPick = e => { const b = e && e.target && e.target.closest && e.target.closest(".msw [data-color]"); return b ? b.dataset.color : null; };
  window.hyRowColor = name => COLORS[name] || "";
  if (!document.getElementById("hy-msw-css")) {
    const st = document.createElement("style"); st.id = "hy-msw-css";
    st.textContent = `.msw { display: flex; align-items: center; gap: 6px; padding: 6px 8px 8px; margin-bottom: 4px; border-bottom: 1px solid var(--line, rgba(127,127,127,.2)); }
.msw > button { flex: none; width: 18px !important; height: 18px !important; min-width: 0 !important; padding: 0 !important; border-radius: 999px !important; background: var(--c) !important;
  border: 2px solid transparent !important; box-shadow: inset 0 0 0 1px rgba(0,0,0,.35); cursor: pointer; transition: border-color .15s cubic-bezier(.32,.72,0,1), scale .15s cubic-bezier(.32,.72,0,1); }
.msw > button:hover { scale: 1.12; } .msw > button.on { border-color: var(--ink, #ececef) !important; }
.hy-rc { position: relative; } .hy-rc::before { content: ""; position: absolute; left: 1px; top: 7px; bottom: 7px; width: 3px; border-radius: 2px; background: var(--hy-rc); pointer-events: none; }
.msw > button.none { --c: transparent; box-shadow: inset 0 0 0 1px var(--sub, #9a9ba3); background: linear-gradient(135deg, transparent 45%, var(--sub, #9a9ba3) 45% 55%, transparent 55%) !important; }`;
    (document.head || document.documentElement).appendChild(st);
  }
  window.hyMenuItem = (attrs, icon, label, keys, extra = "") =>
    `<button role="menuitem" ${attrs}${extra}>${icon && icon[0] === "<" ? icon : IC[icon] || '<span class="mi0"></span>'}<span class="ml">${label}</span>` +
    (keys && keys.length ? `<span class="mk">${keys.map(k => `<kbd>${k}</kbd>`).join("")}</span>` : "") + `</button>`;
  // An item that exists here but does not apply now (owner 2026-10-06: «if some options are not available in the right-click menu, they must
  // simply be grey — I want users to know what functions exist»): it keeps its place, grey, its reason in the tooltip; a click does nothing
  // and the arrow keys pass over it, as macOS does. aria-disabled, not disabled: a disabled button shows no tooltip in some engines.
  //   hyMenuItem('data-act="split"', "split", "Split into pages", ["⌥", "P"], hyMenuOff("Only for a PDF of 2 pages or more"))
  const esc = v => String(v ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  window.hyMenuOff = reason => ` aria-disabled="true" title="${esc(reason)}"`;
  // «Open in <App>» (owner 2026-10-06: «right click can add "open in the app" that is default, maybe you can also see what's the default app
  // to be opened in so you can right away write it there»): the item comes as «Open in default app», and as soon as the server has asked
  // macOS which app opens this kind of file (/api/defaultapp, once per extension) it reads «Open in Adobe Photoshop 2026» with that app's
  // icon. The board's card menu and the library's card menu both have it; a click runs `open` on the server
  const APPS = new Map();   // extension -> the server's answer (a promise while asked)
  const extOf = p => (String(p).match(/\.[^./]+$/) || [""])[0].toLowerCase();
  window.hyOpenItem = attrs => window.hyMenuItem(attrs, "open", t("Open in default app"));
  window.hyOpenFill = (btn, path) => {
    const k = extOf(path); if (!APPS.has(k)) APPS.set(k, fetch(`/api/defaultapp?p=${encodeURIComponent(path)}`).then(r => r.ok ? r.json() : {}).catch(() => ({})));
    return Promise.resolve(APPS.get(k)).then(app => {
      if (!btn || !btn.isConnected || !app || !app.name) return app;
      const l = btn.querySelector(".ml"); if (l) l.textContent = t("Open in {app}", { app: app.name });
      const ic = btn.querySelector("svg, .mi0, img"), im = new Image(15, 15); im.alt = ""; im.style.cssText = "flex:none;display:block";
      im.onload = () => { if (ic && ic.isConnected) ic.replaceWith(im); }; im.src = `/api/appicon?app=${encodeURIComponent(app.path)}`;   // the menu's own icon until the app's is there
      return app;
    });
  };
  window.hyOpenFile = (path, note = (t, k) => (window.hyToast || console.log)(t, k)) =>
    fetch("/api/openfile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .catch(st => { note(st === 403 ? t("This file is outside the library") : st === 404 ? t("The file is not there, or the server was not restarted") : t("The file did not open"), "error"); return null; });
  // «Показать в Finder» for library files (owner 2026-10-05: «a button to open the folder with the file»): the server runs `open -R`,
  // so it works in WebKit, the app's Chromium and a browser on this Mac alike; files of one folder come selected in one window
  window.hyReveal = (paths, note = (t, k) => (window.hyToast || console.log)(t, k)) => {
    const list = [...new Set((paths || []).filter(Boolean))]; if (!list.length) return Promise.resolve(null);
    return fetch("/api/reveal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paths: list }) })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { if (d.skipped) note(t("Opened 5 folders, {n} more not opened", { n: d.skipped }), "info"); return d; })
      .catch(st => { note(st === 403 ? t("This file is outside the library") : st === 404 ? t("The file is not there, or the server was not restarted") : t("Finder did not open"), "error"); return null; });
  };
  // ---- Submenus (owner 2026-10-06, Figma's «Move to page ›»: «move to page is also a good feature»). One item with the app's chevron
  // opens its own panel beside it, the same look as the menu it is in (ui/look.css .hy-sub takes the panel's own background, border and
  // radius), for every menu built with hyMenuItem: the board's #ctx, the library's #lctx, Home's .menu.
  //   hyMenuSub('data-x="1"', "topage", "Move to page", () => hyMenuItem(...) + hyMenuItem(...))
  // build() runs when the panel opens and returns its items' markup; the items act through the menu's own click handler (they sit inside
  // it). A click on the item opens the panel; with { act: true } the item has an action of its own (the menu's handler runs it) and its
  // panel opens on hover and → only («Copy properties» copies all, its panel one kind); { extra } as hyMenuItem's (' disabled').
  // Hover opens after a short intent delay; moving diagonally towards the open panel crosses the items between without closing it (a
  // safe triangle from the pointer to the panel's near edge, as macOS and Figma). Keys: ↑ ↓ move, → opens, ← closes, Enter runs,
  // Esc closes one level. No room on the right: it opens on the left; always inside the window.
  const SUBS = new Map(); let subN = 0;
  window.hyMenuSub = (attrs, icon, label, build, keys, opt = {}) => {
    const k = "s" + (++subN); SUBS.set(k, build); if (SUBS.size > 300) SUBS.delete(SUBS.keys().next().value);
    return window.hyMenuItem(`aria-haspopup="menu" aria-expanded="false" data-hysub="${k}"${opt.act ? ' data-hysubact="1"' : ""} ${attrs}`, icon, label, keys, (opt.off ? window.hyMenuOff(opt.off) : "") + (opt.extra || ""))
      .replace(/<\/button>$/, `<span class="msub">${window.HY_CHEV}</span></button>`);
  };
  const ROOTS = "#ctx, #lctx, .menu, [data-hymenu]";
  const shown = el => !!el && el.isConnected && el.getClientRects().length > 0;
  // a menu is open by its own word, the class «open» every menu of the app sets (the board's #ctx, the library's #lctx, Home's and the image
  // studio's .menu) or data-hymenu="open": a closed menu that only fades out stays laid out with its items, and taking it for open kept
  // ↑ ↓ Enter from the page under it (the image studio's arrows stopped moving layers after any menu, Enter ran an invisible item)
  const isOpen = r => !!r && shown(r) && (r.classList.contains("open") || r.dataset.hymenu === "open");
  const panelOf = el => el.closest(".hy-sub") || el.closest(ROOTS);
  const rootOf = el => { let r = el && el.closest(ROOTS); while (r && r.parentElement && r.parentElement.closest(ROOTS)) r = r.parentElement.closest(ROOTS); return r; };
  const off = b => b.disabled || b.getAttribute("aria-disabled") === "true";
  const itemsOf = panel => [...panel.querySelectorAll('[role=menuitem]')].filter(b => panelOf(b) === panel && !off(b) && shown(b));
  let stack = [], timer = 0, grace = null, last = null, prevItem = null, hoverItem = null;   // stack: the open panels, outermost first
  const prune = () => { while (stack.length && !(shown(stack[stack.length - 1].panel) && shown(stack[stack.length - 1].opener) && isOpen(rootOf(stack[stack.length - 1].opener)))) drop(stack.pop()); };
  const drop = s => { s.panel.remove(); s.opener.setAttribute("aria-expanded", "false"); };
  const level = panel => { const i = stack.findIndex(s => s.panel === panel); return i + 1; };   // 0: the menu itself
  const closeFrom = lv => { while (stack.length > lv) drop(stack.pop()); };
  function place(sub, opener, owner) {
    const pr = owner.getBoundingClientRect(), or = opener.getBoundingClientRect();
    sub.style.left = sub.style.top = "0px"; sub.style.maxHeight = innerHeight - 16 + "px";
    sub.style.overflowY = sub.scrollHeight > sub.clientHeight + 1 ? "auto" : "";   // scrolls only when too tall: a scrolling panel would clip its own submenu
    delete sub.dataset.side;   // measured untransformed: its opening scale grows from the top left corner then
    const o = sub.getBoundingClientRect(), w = sub.offsetWidth, h = Math.min(sub.offsetHeight, innerHeight - 16), padT = parseFloat(getComputedStyle(sub).paddingTop) + sub.clientTop;
    let x = pr.right - 4, side = "right";
    if (x + w > innerWidth - 8) { x = pr.left - w + 4; side = "left"; }
    x = Math.max(8, Math.min(x, innerWidth - 8 - w));
    const y = Math.max(8, Math.min(or.top - padT, innerHeight - 8 - h));
    sub.style.left = x - o.left + "px"; sub.style.top = y - o.top + "px"; sub.dataset.side = side;
  }
  function openSub(opener, focus) {
    prune(); if (!opener.isConnected || !shown(opener)) return;   // the menu closed or was built again while the hover's delay ran
    const owner = panelOf(opener), lv = level(owner); if (!owner) return;
    if (stack[lv] && stack[lv].opener === opener) { closeFrom(lv + 1); if (focus) focusAt(stack[lv].panel, 0); return; }
    closeFrom(lv);
    const build = SUBS.get(opener.dataset.hysub); if (!build) return;
    const sub = document.createElement("div"); sub.className = "hy-sub"; sub.setAttribute("role", "menu");
    sub.innerHTML = build() || ""; owner.appendChild(sub); opener.setAttribute("aria-expanded", "true");
    place(sub, opener, owner); stack.push({ opener, panel: sub });
    opener.dispatchEvent(new CustomEvent("hymenusub", { bubbles: true, detail: { open: true, panel: sub } }));   // the board tells the library page its menu's room
    if (focus) focusAt(sub, 0);
  }
  window.hyMenuSubClose = () => { clearTimeout(timer); closeFrom(0); };
  const focusAt = (panel, i) => { const L = itemsOf(panel); if (L.length) L[(i + L.length) % L.length].focus({ preventScroll: true }); };
  // the safe triangle: from where the pointer left the opener (a little behind it) to the near edge's two corners of the open panel
  const inTri = (p, a, b, c) => { const d = (u, v, w) => (u.x - w.x) * (v.y - w.y) - (v.x - w.x) * (u.y - w.y), d1 = d(p, a, b), d2 = d(p, b, c), d3 = d(p, c, a);
    return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0)); };
  function hover(item) {
    clearTimeout(timer); grace = null;
    if (!item) return;
    const owner = panelOf(item), lv = level(owner), open = stack[lv];
    if (open && open.opener === item) { closeFrom(lv + 1); return; }
    if (item.dataset.hysub && !off(item)) timer = setTimeout(() => openSub(item), 110);   // a short intent delay: passing over it opens nothing
    else if (open) timer = setTimeout(() => closeFrom(lv), 110);
  }
  document.addEventListener("pointermove", e => {
    if (e.pointerType === "touch") return;
    const p = { x: e.clientX, y: e.clientY }, it = e.target.closest && e.target.closest("[role=menuitem]"), item = it && isOpen(rootOf(it)) ? it : null;
    if (!stack.length && !item) { last = p; prevItem = hoverItem = null; return; }   // the board under the pointer: nothing to do
    prune();
    if (item !== prevItem) {
      const s = prevItem && stack.find(x => x.opener === prevItem);
      if (s && last) {   // just left an opener: towards its panel, the items on the way do not count for a moment
        const r = s.panel.getBoundingClientRect(), left = s.panel.dataset.side === "left", ex = left ? r.right : r.left, back = left ? 3 : -3;
        grace = { a: { x: last.x + back, y: last.y }, b: { x: ex, y: r.top - 4 }, c: { x: ex, y: r.bottom + 4 }, until: performance.now() + 400, lv: level(s.panel) };
      }
      prevItem = item;
    }
    last = p;
    if (item && document.activeElement && document.activeElement !== item && document.activeElement.matches && document.activeElement.matches("[role=menuitem]") && rootOf(document.activeElement)) document.activeElement.blur();
    hoverItem = item;
    if (grace && performance.now() < grace.until && inTri(p, grace.a, grace.b, grace.c) && !(item && panelOf(item) === (stack[grace.lv - 1] || {}).panel)) {
      clearTimeout(timer); timer = setTimeout(() => hover(hoverItem), grace.until - performance.now());   // stopped on the way: then it counts
      return;
    }
    if (item) hover(item); else { clearTimeout(timer); grace = null; }
  }, true);
  document.addEventListener("click", e => {
    const no = e.target.closest && e.target.closest("[role=menuitem]");
    if (no && off(no) && isOpen(rootOf(no))) { e.preventDefault(); e.stopImmediatePropagation(); return; }   // grey: nothing, the menu stays
    const op = e.target.closest && e.target.closest("[data-hysub]"); if (!op || !isOpen(rootOf(op)) || op.dataset.hysubact) return;
    e.preventDefault(); e.stopPropagation(); clearTimeout(timer); openSub(op, e.detail === 0);   // Enter or Space on it (detail 0): into the panel
  }, true);
  addEventListener("keydown", e => {
    prune();
    // the key's own test first: the open menus are looked for in the whole page and measured (a forced layout), on every key typed
    // into a note too (2026-10-08, the «Renderings» page of 48 000 elements: 21 ms a key with the CPU 4× slower)
    if (e.metaKey || e.ctrlKey || e.altKey || (e.target.closest && e.target.closest("input, textarea, [contenteditable=true]"))) return;
    const roots = [...document.querySelectorAll(ROOTS)].filter(r => isOpen(r) && !r.parentElement.closest(ROOTS) && r.querySelector("[role=menuitem]"));
    if (!roots.length) return;
    const a = document.activeElement, focused = a && a.matches && a.matches("[role=menuitem]") && roots.includes(rootOf(a)) ? a : null;
    const cur = focused || (hoverItem && shown(hoverItem) && roots.includes(rootOf(hoverItem)) ? hoverItem : null);
    const panel = cur ? panelOf(cur) : stack.length ? stack[stack.length - 1].panel : roots[roots.length - 1];
    const L = itemsOf(panel), i = cur ? L.indexOf(cur) : -1, k = e.key;
    const eat = () => { e.preventDefault(); e.stopImmediatePropagation(); };
    if (k === "ArrowDown" || k === "ArrowUp") { eat(); hoverItem = null; focusAt(panel, i < 0 ? (k === "ArrowDown" ? 0 : -1) : i + (k === "ArrowDown" ? 1 : -1)); }
    else if (k === "ArrowRight") { eat(); if (cur && cur.dataset.hysub && !off(cur)) { clearTimeout(timer); openSub(cur, true); } }
    else if (k === "ArrowLeft") { eat(); const lv = level(panel); if (lv) { const s = stack[lv - 1]; closeFrom(lv - 1); s.opener.focus({ preventScroll: true }); } }
    else if (k === "Enter") { if (!cur) return; eat(); if (off(cur)) return; if (cur.dataset.hysub && !cur.dataset.hysubact) { clearTimeout(timer); openSub(cur, true); } else cur.click(); }
    else if (k === "Escape" && stack.length) { eat(); const s = stack[stack.length - 1]; closeFrom(stack.length - 1); s.opener.focus({ preventScroll: true }); }
  }, true);
})();
