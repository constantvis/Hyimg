// ⌘C on one board, ⌘V on another (P4 B-05, П4 audit 2026-10-10: the paste on another board was the copy's link as a heading). The board's
// own clipboard is cv.clip in localStorage (canvas.html copySel), and each board is its own address, so it reached only one project's
// pages. A copy now also goes to the app's clipboard file beside the settings (review/boardclip.py, as the properties clipboard ⌥⌘C does);
// a paste takes the newer of the two. A copy from another library first brings its files here (pictures as pasted ones, a video or a
// PDF byte for byte, or where this library already has the same bytes); a card whose file is gone is left out and the note counts it.
// A Hyimg link to things on another board (a pasted text, as ⌘C puts the link on the system clipboard) pastes the copy itself, never a
// heading with the link; with nothing copied the note says to copy them there with ⌘C.
//   hyBoardClip.put(clip)       after ⌘C: the copy to the app's clipboard
//   hyBoardClip.quick(local, t) ⌘V can paste this page's own copy at once: it is the newest the app's clipboard was last seen to hold
//                               (asked again on focus and when the page shows), and the text pasted is no link to another board
//   hyBoardClip.get(local)      otherwise: { clip, missing } the newer copy, its paths this library's; missing, the cards left out
//   hyBoardClip.has()           the menu's Paste: something to paste, here or from another board
//   hyBoardClip.isLink(text)    a Hyimg link to things on a board, this one's or another's
(() => {
  if (window.hyBoardClip) return;
  const post = (path, body) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then(r => (r.ok ? r.json() : {})).catch(() => ({}));
  const local = () => { try { return JSON.parse(localStorage.getItem("cv.clip") || "null"); } catch { return null; } };
  let seen = null;   // the app's copy as last asked (focus, a paste): {at, n}
  function put(clip) { seen = { at: clip.at, n: clip.items.length }; post("/api/boardclip", { clip }); }
  async function look() {
    const d = await post("/api/boardclip", { read: true });
    seen = d && d.clip ? { at: d.clip.at || 0, n: (d.clip.items || []).length } : null;
    return d;
  }
  async function get(mine) {
    const d = await look(), clip = d && d.clip;
    if (!clip || !Array.isArray(clip.items) || ((mine && mine.at) || 0) >= (clip.at || 0)) return { clip: mine, missing: 0 };
    if (d.here) return { clip, missing: 0 };
    const t = await post("/api/boardclip/take", {}), map = t.map || {}, gone = new Set(t.missing || []);
    const out = new Set(clip.items.filter(it => it.path && (gone.has(it.path) || !map[it.path])).map(it => it.key));
    const items = clip.items.filter(it => !out.has(it.key)).map(it => {
      const o = { ...it, ...(it.path ? { path: map[it.path] } : {}) };
      if (Array.isArray(o.to)) o.to = o.to.filter(k => !out.has(k));
      return o;
    });
    const groups = (clip.groups || []).map(g => ({ ...g, members: g.members.filter(m => !out.has(m)) }));
    return { clip: { ...clip, items, groups }, missing: out.size };
  }
  const quick = (mine, t) => !!(mine && (mine.items || []).length) && !(seen && seen.at > (mine.at || 0))
    && !(t && isLink(t) && (() => { try { return new URL(t.trim()).origin !== location.origin; } catch { return true; } })());
  const has = () => ((local() || {}).items || []).length > 0 || !!(seen && seen.n && seen.at > ((local() || {}).at || 0));
  // a Hyimg link to things: http(s)://localhost|127.0.0.1:<port>/?view=canvas…&obj=…, or the app's hyimg:// with obj
  const isLink = t => {
    try { const u = new URL(String(t || "").trim()); return u.searchParams.has("obj") && (u.protocol === "hyimg:" || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(u.hostname)); }
    catch { return false; }
  };
  addEventListener("focus", look); document.addEventListener("visibilitychange", () => { if (!document.hidden) look(); });
  look();
  window.hyBoardClip = { put, get, quick, has, isLink };
})();
