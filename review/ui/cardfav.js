// The ♥ on an HTML card, as on a picture (owner 2026-10-08: «И почему пропали лайки справа в углу на HTML?»). The board's ♥ was built
// only into a picture's element (.it; the marks of 2026-10-06 said «a plugin card has no ♥»), so the HTML pages that took the place of
// the pictures in the concept rounds (Dev Studio's html cards, the frames plugin's HTML frames) never had one. A card whose src is an
// .html page has the picture's ♥ for that file now: the same mark (.mk.mk-fav, slot 0 of the top right row, its slot kept by the marks'
// law), shown when liked or under the pointer, toggled by a click on it, F, Info's ♥ and the selection's ♥, all through toggleFav and
// POST /api/fav. So it lives where a picture's lives, feedback.fav in the file's json (a page's is <page>.html.json): the library's ♥ of
// that file is the same one, and copies of a page agree.
// A page outside the library (html/, a project's concept rounds) is not in the list the board loads (byPath): its ♥ is asked once, a few
// pages a request, with GET /api/fav?p= (review/favread.py), and kept in byPath as a ♥ pressed on a picture the list has not brought yet.
// canvas.html calls: path(it) (the file a thing's ♥ is about: a picture's path, an HTML card's page, else null), paint(el, it) from a
// plugin card's render (true when the card has the ♥, for the law), info(button, it) for Info's ♥, allOn(ids) for the selection's ♥.
(() => {
  const PAGE = /\.html?$/i, PART = 40;
  const path = it => !it ? null : !it.type ? it.path || null : typeof it.src === "string" && PAGE.test(it.src) ? it.src : null;
  const favOf = p => !!(((byPath.get(p) || {}).feedback || {}).fav);
  const asked = new Set(); let queue = [], timer = 0;

  function ask(p) {
    if (byPath.has(p) || asked.has(p)) return;
    asked.add(p); queue.push(p); if (!timer) timer = setTimeout(flush, 0);
  }
  async function flush() {
    timer = 0; const ps = queue; queue = []; let got = false;
    for (let i = 0; i < ps.length; i += PART) {
      const part = ps.slice(i, i + PART);
      try {
        const r = await fetch("/api/fav?" + part.map(p => "p=" + encodeURIComponent(p)).join("&")); if (!r.ok) continue;   // a server before this: hover ♥ only
        const fb = (await r.json()).feedback || {};
        for (const p of part) if (!byPath.has(p)) { byPath.set(p, { path: p, feedback: fb[p] || {} }); got = got || !!fb[p]; }   // a ♥ pressed meanwhile stays
      } catch (e) { part.forEach(p => asked.delete(p)); }   // asked again at the next render
    }
    if (got) render();
  }
  // the mark on a plugin card: added once after the plugin's own content (a plugin that redraws its card gets it back at the next render)
  function paint(el, it) {
    const p = path(it); let h = el._fav && el._fav.parentNode === el ? el._fav : el.querySelector(":scope > .mk-fav");   // kept on the card: paint runs on every render
    if (!p) { if (h) { h.remove(); el._fav = null; el.classList.remove("faved"); } return false; }
    if (!h) {
      el.insertAdjacentHTML("beforeend", `<button class="mk mk-tr mk-fav lk" title="${T("♥ Like · F")}" aria-label="${T("Like")}">${mkSvg("heart")}</button>`);
      h = el.lastElementChild;
    }
    el._fav = h;
    ask(p); const on = favOf(p); if (el.classList.contains("faved") !== on) el.classList.toggle("faved", on);
    return true;
  }
  function info(b, it) {
    const p = path(it); b.style.display = p ? "" : "none"; if (!p) return;
    const on = favOf(p); b.classList.toggle("on", on); b.title = on ? T("Remove ♥ · F") : T("♥ Like · F");
  }
  function allOn(ids) { const ps = ids.map(id => path(board.items[id])).filter(Boolean); return ps.length > 0 && ps.every(favOf); }
  window.hyCardFav = { path, paint, info, allOn };
})();
