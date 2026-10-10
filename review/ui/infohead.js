// The Info card's header (owner 2026-10-09, round 15 «Info · the header», liked as drawn; round 14: «лайк справа сверху, и там же кнопка
// Открыть ... и какая-то информация: размер, разрешение, формат, если видео — то его данные», «картинку мы уже выделили и видим — нужно
// компактно упаковать»). One selected picture, video, copy of a picture (an instance), 3D scene or HTML page shows its name, one line of
// facts read from the file and ♥ · Open · … at the top right; a video has its trim bar under it. A sticky note keeps its header as it was
// (plain()); a group has no Info at all (owner 2026-10-10: «вообще picker for group не нужен»). DESIGN.md «Шапка Info».
// Where the facts come from: a picture's size in px from the file's header (POST /api/sizes, once a file), its bytes and format from the
// library's list (byPath); a video's size, length, fps and codecs from the server's ffprobe (server.py video_probe); a plugin's card from
// its info() (name, meta). Uses canvas.html's board, sel, byPath, EL, PLG, EMBED and its helpers (vtime, fmtSize, origOf, goTo, Q).
(() => {
  const $ = s => document.querySelector(s);
  const DIMS = new Map();   // path -> [w, h], or null while the server is asked
  const RATIOS = [[1, 1], [5, 4], [4, 3], [3, 2], [16, 10], [16, 9], [2, 1], [21, 9], [3, 1]];
  const CODEC = { h264: "H.264", hevc: "HEVC", vp8: "VP8", vp9: "VP9", av1: "AV1", prores: "ProRes", mpeg4: "MPEG-4", mjpeg: "MJPEG", gif: "GIF" };
  let act = null, cur = null, tick = 0;   // what Open does now; the id the header is about; the playhead's timer

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
    const b = $("#info"); b.dataset.kind = kind; b.classList.remove("hx"); show("#iMore", false); $("#iN").title = $("#iM").title = ""; trim(null); cur = null; act = null;
  }
  function set(kind, id, name, facts, o) {
    const b = $("#info"); b.dataset.kind = kind; b.classList.add("hx"); cur = id;
    $("#iN").textContent = name; $("#iN").title = name;
    const line = facts.filter(Boolean).join(" · "); $("#iM").textContent = line; $("#iM").title = line;
    act = o.open || null; show("#iOpen", !!act);   // every Open says ↵, which runs it on the one selected card (P4 B-36)
    if (act) { $("#iOpen").textContent = act.label; $("#iOpen").title = (act.title || act.label).replace(/ · ↵$/, "") + " · ↵"; }
    show("#iMore", !!EL.get(id)); $("#iE").textContent = "";
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
    set(kind, id, name, facts, { open: copy ? { label: T("To the original"), fn: () => goTo(o, id) }
      : { label: T("Open"), title: T("Open the frame to view and rate it"),
        fn: () => EMBED ? parent.postMessage({ type: "openFrame", path: it.path }, location.origin) : open(`/img?p=${encodeURIComponent(it.path)}`, "_blank") } });
    // a copy is the same file: its ♥ is the original's, shown and set here too (owner decision 2026-10-10, P4 B-37 a)
    show("#iFav", true); $("#iFav").classList.toggle("on", !!f.fav); $("#iFav").title = f.fav ? T("Remove ♥ · F") : T("♥ Like · F");
    trim(vid && m.duration ? { id, it, d: m.duration } : null);
  }

  // a plugin's card: its own name and line (info()), Open is what a double click does (its Studio)
  function card(id, it, inf) {
    const P = PLG[it.type] || {}, can = !!P.dblclick;
    const kind = it.type === "model3d" ? "3d" : hyCardFav.path(it) ? "html" : it.type;
    set(kind, id, inf.name || it.type, [inf.meta], { open: can && !P.standIn ? { label: T("Open"), title: T("Open · ↵"),
      fn: () => { if (!(window.hyPlugBoard && hyPlugBoard.open(it.type, id))) P.dblclick && P.dblclick(id); } } : null });
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

  addEventListener("DOMContentLoaded", () => {
    $("#iOpen").onclick = () => { if (act) act.fn(); };
    // «…»: the thing's own menu (the board's right click), under the button
    $("#iMore").onclick = e => {
      const el = cur && EL.get(cur); if (!el) return; e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect();
      el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: r.left, clientY: r.bottom + 4 }));
    };
  });
  // ↵ on the board with one card selected: what Open does (canvas.html's keys, ui/boardkeys.js); false when it has none
  // (not «open»: the picture's Open calls the window's open() from this same scope)
  const openNow = () => { if (!act || !cur || $("#info").style.display === "none" || $("#iOpen").style.display === "none") return false; act.fn(); return true; };
  window.hyInfoHead = { pic, card, plain, ratio, open: openNow };
})();
