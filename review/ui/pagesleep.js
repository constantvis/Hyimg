// Pages switch fast (owner 2026-10-08, «Board structure» › «Pages switch fast»: «pages stay asleep in the background, coming back is
// instant»). Before, a page switch threw away every element of the page left and the way back built them again: each picture a new <img>,
// loaded and decoded anew. Now the page left falls asleep: its pictures, notes, headings, timelines and group frames are taken out of the
// board with their state (place, marks, the loaded picture) and kept with the board and its save base as they were. Coming back puts them
// in again at once, with the page's own camera, and draws them; then the page is read from the server as always and render() brings the
// elements up to date (what an agent or another window changed meanwhile moves, what was removed goes, what is new is made).
// Plugin cards (3D, HTML, image frames) are not kept: a plugin owns what is inside them, they are made again as before.
// A sleeping page gives its memory back after the board's own sleep time (Settings › Board › «Sleep background boards», Never keeps it),
// at most MAX pages and ELS elements are kept, the oldest go first. canvas.html calls put (leaving a page) and take (coming to one).
(() => {
  const MAX = 4, ELS = 6000, S = new Map();   // page -> { els, gels, board, base, at, timer }
  const minutes = () => { try { const v = Number(setOf("sleep")); return Number.isFinite(v) ? v : 10; } catch { return 10; } };
  function drop(page) { const s = S.get(page); if (!s) return; clearTimeout(s.timer); S.delete(page); }
  function trim() {
    let n = [...S.values()].reduce((a, s) => a + s.els.size, 0);
    for (const [page, s] of [...S].sort((a, b) => a[1].at - b[1].at)) {
      if (S.size <= MAX && n <= ELS) break;
      n -= s.els.size; drop(page);
    }
  }
  // the page left: its elements out of the board, kept; EL and GEL are empty after
  function put(page, EL, GEL, b, base) {
    drop(page);
    const els = new Map(), gels = new Map();
    for (const [id, el] of EL) { el.remove(); if (!el.classList.contains("plg")) els.set(id, el); }
    for (const [id, el] of GEL) { el.remove(); gels.set(id, el); }
    EL.clear(); GEL.clear();
    const s = { els, gels, board: b, base, at: Date.now() }, m = minutes();
    if (m > 0) s.timer = setTimeout(() => drop(page), m * 60000);
    S.set(page, s); trim();
  }
  // the page come to: its elements back with the board as it was left and its camera, drawn at once; false when it was not asleep
  function take(page) {
    const s = S.get(page); if (!s) return false;
    clearTimeout(s.timer); S.delete(page);
    const gEl = document.querySelector("#groups"), iEl = document.querySelector("#items");
    for (const [id, el] of s.gels) { gEl.appendChild(el); GEL.set(id, el); }
    for (const [id, el] of s.els) { iEl.appendChild(el); EL.set(id, el); }
    board = s.board; if (s.base) BASE = s.base;
    try { const c = JSON.parse(pref("cam." + page, "null")); if (c) cam = c; } catch {}
    try { render(); } catch (e) { console.error("pagesleep", e); }
    return true;
  }
  window.hyPageSleep = { put, take, drop, has: page => S.has(page), get pages() { return [...S.keys()]; } };
})();
