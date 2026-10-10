// The Info card's header (owner 2026-10-09, round 15 «Info · the header», liked as drawn; round 14: «лайк справа сверху, и там же кнопка
// Открыть ... и какая-то информация: размер, разрешение, формат, если видео — то его данные», «картинку мы уже выделили и видим — нужно
// компактно упаковать»). One selected picture, video, copy of a picture (an instance), 3D scene or HTML page shows its name, one line of
// facts read from the file and ♥ · Open ▾ at the top right; a video has its trim bar under it. A sticky note keeps its header as it was
// (plain()); a group has no Info at all (owner 2026-10-10: «вообще picker for group не нужен»). DESIGN.md «Шапка Info».
// Round 18 (owner 2026-10-10): Open has an arrow ▾ (question 7, ★ yes: «Preview, в приложении, в Finder, по типу файла»), the app's one
// split button <hy-split> (ui/hy/split.js), each kind its own rows and its main one on ↵, then a line and the file's rows: a picture its
// Image Studio and Preview (round 19, switch-b.html), a video Preview, a 3D scene or HTML page its Studio, an HTML page also its browsers;
// then Open in its app, Show in Finder, Copy path, Copy as image. The «…» button is gone (question
// 8: «А это тогда можно убрать. Зачем она здесь? Можно по правой кнопке просто это делать»): it only opened the card's right-click menu.
// Where the facts come from: a picture's size in px from the file's header (POST /api/sizes, once a file), its bytes and format from the
// library's list (byPath); a video's size, length, fps and codecs from the server's ffprobe (server.py video_probe); a plugin's card from
// its info() (name, meta). Uses canvas.html's board, sel, byPath, EL, PLG, EMBED and its helpers (vtime, fmtSize, origOf, goTo, Q).
(() => {
  const $ = s => document.querySelector(s);
  const DIMS = new Map();   // path -> [w, h], or null while the server is asked
  const RATIOS = [[1, 1], [5, 4], [4, 3], [3, 2], [16, 10], [16, 9], [2, 1], [21, 9], [3, 1]];
  const CODEC = { h264: "H.264", hevc: "HEVC", vp8: "VP8", vp9: "VP9", av1: "AV1", prores: "ProRes", mpeg4: "MPEG-4", mjpeg: "MJPEG", gif: "GIF" };
  let act = null, cur = null, tick = 0;   // Open's main row now; the id the header is about; the playhead's timer

  function ratio(w, h) {   // a common ratio within 1 %, else none (an odd size says nothing as a ratio)
    for (const [a, b] of RATIOS) for (const [x, y] of a === b ? [[a, b]] : [[a, b], [b, a]]) if (Math.abs(w / h / (x / y) - 1) < .01) return `${x}:${y}`;
    return "";
  }
  function dims(p) {
    if (DIMS.has(p)) return DIMS.get(p);
    DIMS.set(p, null);
    fetch("/api/sizes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paths: [p] }) })
      .then(r => r.json()).then(d => { if (!d[p]) return; DIMS.set(p, d[p]); if (cur && board.items[cur] && board.items[cur].path === p) renderInfo(); })
      .catch(() => DIMS.delete(p));
    return null;
  }
  const wxh = wh => wh && wh[0] ? `${wh[0]} × ${wh[1]}` : "";
  const show = (s, on) => { $(s).style.display = on ? "" : "none"; };

  // a sticky note: the header as it was, without the new buttons
  function plain(kind) {
    const b = $("#info"); b.dataset.kind = kind; b.classList.remove("hx"); if ($("#iOpen").close) $("#iOpen").close(); $("#iN").title = $("#iM").title = ""; trim(null); cur = null; act = null;
  }
  function set(kind, id, name, facts, o) {
    const b = $("#info"); b.dataset.kind = kind; b.classList.add("hx");
    if (cur !== id && $("#iOpen").close) $("#iOpen").close();   // Open's menu was another card's
    cur = id;
    $("#iN").textContent = name; $("#iN").title = name;
    const line = facts.filter(Boolean).join(" · "); $("#iM").textContent = line; $("#iM").title = line;
    // every Open says ↵, which runs its main row on the one selected card (P4 B-36); the arrow has the rest
    const rows = o.open || [], op = $("#iOpen"); act = rows.find(r => r.main) || null; show("#iOpen", !!act);
    if (act) { op.items = rows; op.title = (act.title || act.label).replace(/ · ↵$/, "") + " · ↵"; op.setAttribute("tip", op.title); op.setAttribute("label", T("More ways to open")); }
    $("#iE").textContent = "";
  }

  // a picture, a video, a PDF, or a copy of one of them (the first one on the page is the original: canvas.html origOf)
  function pic(id, it, m) {
    const f = m.feedback || {}, name = it.path.split("/").pop(), vid = m.kind === "video", o = origOf(id), copy = !!o && o !== id;
    const wh = vid ? m.vsize : m.kind === "pdf" ? null : dims(it.path), size = m.size ? fmtSize(m.size) : "", ext = m.ext || (name.split(".").pop() || "").toUpperCase();
    let kind = vid ? "video" : m.kind === "pdf" ? "pdf" : "image", facts;
    if (copy) {
      const same = Object.keys(board.items).filter(k => board.items[k].path === it.path);
      kind = "instance"; facts = [T("copy of {name}", { name: Q(name) }), T("{i} of {n}", { i: same.indexOf(id) + 1, n: same.length }), wxh(wh)];
    } else if (vid) {
      const fps = m.fps ? T("{n} fps", { n: +(+m.fps).toFixed(2) }) : "", codec = m.vcodec ? CODEC[m.vcodec] || String(m.vcodec).toUpperCase() : "";
      facts = [wxh(wh) || (m.duration ? "" : T("video")), m.duration ? vtime(m.duration) : "", fps, codec, m.acodec ? T("sound") : "", size];
    } else facts = [wxh(wh), m.pages ? T("{n} pages", { n: m.pages }) : "", ext, size, wh ? ratio(wh[0], wh[1]) : ""];
    const view = () => EMBED ? parent.postMessage({ type: "openFrame", path: it.path }, location.origin) : open(`/img?p=${encodeURIComponent(it.path)}`, "_blank");
    // a picture (not a copy, a video or a PDF) opens Image Studio first, as its double click does (owner 2026-10-10, round 19 switch-b.html:
    // «Тоже все отлично. Очень нравится. Делаем.»): «Image Studio ↵», then Preview, a line, the file's rows
    const img = !copy && !m.kind && studioOf("image"), pv = { label: T("Preview"), short: T("Open"), icon: "eye", title: T("Open the frame to view and rate it"), run: view };
    const head = copy ? [{ label: T("To the original"), icon: "goTo", main: true, run: () => goTo(o, id) }, pv]
      : img ? [{ label: img.name, short: T("Open"), icon: img.icon, main: true, run: () => { if (!MODES.enter("image", [id])) view(); } }, pv] : [{ ...pv, main: true }];
    set(kind, id, name, facts, { open: [...head, { sep: true }, ...fileRows(id, it.path, true)] });
    // a copy is the same file: its ♥ is the original's, shown and set here too (owner decision 2026-10-10, P4 B-37 a)
    show("#iFav", true); $("#iFav").classList.toggle("on", !!f.fav); $("#iFav").title = f.fav ? T("Remove ♥ · F") : T("♥ Like · F");
    trim(vid && m.duration ? { id, it, d: m.duration } : null);
  }

  // a plugin's card: its own name and line (info()), Open is what a double click does (its Studio)
  function card(id, it, inf) {
    const P = PLG[it.type] || {}, can = !!P.dblclick && !P.standIn, page = hyCardFav.path(it);
    const kind = it.type === "model3d" ? "3d" : page ? "html" : it.type, file = it.scene || page || "";
    // the main row is the card's Studio, named as the dock's switch names it (3D Studio, Dev Studio), else «Open»
    const st = studioOf(kind === "html" ? "dev" : kind);
    const main = can ? { label: st ? st.name : T("Open"), icon: st ? st.icon : "open", main: true, title: T("Open · ↵"),
      run: () => { if (!(window.hyPlugBoard && hyPlugBoard.open(it.type, id))) P.dblclick && P.dblclick(id); } } : null;
    set(kind, id, inf.name || it.type, [inf.meta], { open: main ? [main, { sep: true }, ...(page ? browsers(page) : []), ...fileRows(id, file, false)] : [] });
    hyCardFav.info($("#iFav"), it); trim(null);
    window.hyEdited?.($("#iE"), BOARD, id, Object.values(it));
  }

  // a video's trim bar: the part kept of the whole clip, where it plays now; a click opens Crop & Trim (⇧C)
  function trim(v) {
    const t = $("#iTrim"); clearInterval(tick); show("#iTrim", !!v); if (!v) return;
    const [a, b] = Array.isArray(v.it.trim) ? v.it.trim : [0, v.d], pc = x => Math.max(0, Math.min(100, x / v.d * 100)).toFixed(2) + "%";
    t.innerHTML = `<span class="tr"><i style="left:${pc(a)};right:calc(100% - ${pc(b)})"></i><b></b></span><span>${T("{a} – {b} of {d}", { a: vtime(a), b: vtime(b), d: vtime(v.d) })}</span>`;
    t.title = T("Crop the picture, trim the start and the end · ⇧C"); t.onclick = () => startCrop(v.id);
    const head = () => { const s = VS.get(v.id), x = s && s.v ? s.v.currentTime : null, hb = t.querySelector("b"); hb.style.display = x == null ? "none" : ""; if (x != null) hb.style.left = pc(x); };
    head(); tick = setInterval(() => { if (cur !== v.id || $("#info").style.display === "none") return clearInterval(tick); head(); }, 250);
  }

  // a Studio of the dock's switch (its key: image, 3d, dev): its name as the switch names it and a dot in its colour, or null without it
  function studioOf(k) {
    const seg = window.MODES && MODES.el && MODES.el.querySelector(`[data-mode="${k}"]`); if (!seg || !seg.dataset.name) return null;
    const c = seg.style.getPropertyValue("--hy-mode-c") || "var(--sel)";
    return { name: seg.dataset.name, icon: `<span class="oi-ic oi-dot" style="--oi-c:${c.replace(/"/g, "")}"></span>` };
  }
  // the rows every file has: its app (named as macOS names it, ui/menu.js hyOpenFill), Finder, its path, its picture on the clipboard (⇧⌘C)
  function fileRows(id, path, app) {
    if (!path) return [];
    return [...(app ? [{ label: T("Open in default app"), icon: "open", row: b => window.hyOpenFill && hyOpenFill(b, path), run: () => hyOpenFile(path, toast) }] : []),
      { label: T("Show in Finder"), icon: "folder", run: () => hyReveal([path], toast) },
      { label: T("Copy path"), icon: "copy", run: () => copyText(path, T("Path copied")) },
      { label: T("Copy as image"), icon: "image", keys: ["⇧", "⌘", "C"], run: () => hyCopyImage.key([id]) }];
  }
  // an HTML page in the browsers of this Mac (the app's list, ui/hy/openin.js hyBrowsers), or in a new tab
  function browsers(page) {
    const url = new URL(`/lib/${page.split("/").map(encodeURIComponent).join("/")}`, location.href).href, g = window.hyBrowsers && hyBrowsers.list;
    if (!g) return [{ label: T("Open in browser"), icon: "open", run: () => open(url, "_blank", "noopener") }];
    return g.browsers.map(b => ({ label: T("Open in {app}", { app: b.name }), icon: b.icon ? `<img class="oi-ic" alt="" src="${b.icon}">` : "open", run: () => hyBrowsers.open(url, b.id) }));
  }
  // ↵ on the board with one card selected: what Open's main row does (canvas.html's keys, ui/boardkeys.js); false when it has none
  // (not «open»: the picture's Open calls the window's open() from this same scope)
  const openNow = () => { if (!act || !cur || $("#info").style.display === "none" || $("#iOpen").style.display === "none") return false; act.run(); return true; };
  window.hyInfoHead = { pic, card, plain, ratio, open: openNow };
})();
