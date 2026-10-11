// The first rows of the board's right-click menu (round 20, question 13 B, owner 2026-10-11 on open-b.html: «да вот так лучше»; board audit
// B-18, panels audit P-12). The menu of one card starts with the card's main row, the same one its Info card's Open ▾ starts with, the Studio
// chip over it names and its double click runs: «Image Studio ↵», «3D Studio ↵», «Dev Studio ↵», a video's «View ↵», a copy's «To the
// original ↵» (ui/infohead.js hyInfoHead.rows). Crop ⇧C comes second for a picture, a PDF or a video («Crop & Trim»), then «Open with ›»,
// the apps of this Mac that open the file (ui/menu.js hyOpenWith). Before, the menu started with «Open in Preview» and had neither the
// Studio nor Crop, the first buttons of the bar over the card. The keys stay in key caps, the decision of 2026-10-04 (B, not A).
// The empty board's menu makes what «+» in the dock makes, at the click: a note N, a text T, a timeline L, a plugin's card (B-18).
//   hyCtxMain.top(ids, id)      the rows for the selection, in canvas.html's form [act, icon, label, keys] (+ .sub, .off)
//   hyCtxMain.empty()           the rows of the empty board
//   hyCtxMain.act(b, ids, id, p)   a row of these ran: true when it was one of them (p: the click on the board)
(() => {
  if (window.hyCtxMain) return;
  const css = document.createElement("style"); css.id = "hy-ctxmain-css";
  // a Studio's row wears the Studio's dot where the icon stands, as in Open ▾ (ui/hy/openin.css .oi-dot); the menu's icons are 15 px
  css.textContent = `#ctx .oi-dot { display: grid; place-items: center; width: 15px; height: 15px; flex: none; }
#ctx .oi-dot::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--oi-c, var(--sel)); }
#ctx [data-act^="mk:"] > svg { width: 15px; height: 15px; flex: none; }`;
  (document.head || document.documentElement).appendChild(css);
  let MAIN = null;   // the main row of the menu open now

  function top(ids, id) {
    MAIN = null; const out = [], it = id && board.items[id];
    if (ids.length === 1 && it && window.hyInfoHead && hyInfoHead.rows) {
      const m = hyInfoHead.rows(id).find(r => r.main);
      if (m) { MAIN = m; const ic = m.icon && m.icon[0] === "<" ? m.icon : m.icon || "open"; out.push(["main", ic, m.label, ["↵"]]); }
    }
    const pics = ids.filter(i => board.items[i] && isPic(board.items[i]));
    if (pics.length && pics.length === ids.length) {
      const one = ids.length === 1, vid = one && isVid(it);
      out.push(Object.assign(["crop", "crop", vid ? T("Crop & Trim") : T("Crop"), ["⇧", "C"]], one ? {} : { off: T("Crop one picture at a time") }));
      const path = one ? fileOf(it) : "";
      if (path && window.hyOpenWith) hyOpenWith.ask(path);   // asked now: the submenu has its apps when it opens
      const sub = path && window.hyOpenWith ? { sub: () => hyOpenWith.rows(path, 'data-act="openwith"') } : { sub: () => "", off: T("Select one file") };
      out.push(Object.assign(["openwith", "open", T("Open with")], sub));
    }
    return out;
  }
  function empty() {
    return window.hyBoardDock && hyBoardDock.list ? hyBoardDock.list(15).map(x => ["mk:" + x.k, x.icon, x.label, x.keys]) : [];
  }
  function act(b, ids, id, p) {
    const a = b.dataset.act;
    if (a === "main") { if (MAIN && MAIN.run) MAIN.run(); return true; }
    if (a === "crop") { if (ids.length === 1) startCrop(ids[0]); return true; }
    if (a === "openwith") return true;   // the app's row opened the file itself (ui/menu.js, one listener for every menu)
    if (a.startsWith("mk:")) { hyBoardDock.make(a.slice(3), p); return true; }
    return false;
  }
  window.hyCtxMain = { top, empty, act };
})();
