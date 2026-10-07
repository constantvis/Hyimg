// A video card in the library plays under the pointer (owner 2026-10-06: «video in the media library should play on hover too»), as on
// the board: muted and looping over the card's picture, shown only once it really plays so the picture never blinks black, and on
// leave it fades back to the picture. One element for the whole library, moved from card to card; a quick sweep of the pointer over
// many cards starts nothing (it waits HOLD ms on a card). Where the engine cannot play the file's codecs it plays the server's WebM copy
// (ui/video.js). The page's cards are <button class="card" data-i> over its list `view`; the card's <img> sets the frame to cover.
(() => {
  if (window.hyLibVideo) return;
  const HOLD = 140, FADE = 200;
  const v = document.createElement("video");
  v.muted = true; v.loop = true; v.playsInline = true; v.preload = "none"; v.disablePictureInPicture = true; v.setAttribute("disableremoteplayback", "");
  v.className = "lvid";
  const st = document.createElement("style");
  st.textContent = `.card > video.lvid { position: absolute; z-index: 1; pointer-events: none; opacity: 0; transition: opacity .2s cubic-bezier(.32,.72,0,1); background: transparent; }
.card > video.lvid.on { opacity: 1; }
.card:has(> video.lvid) > :is(.st, .nm, .sc, .pick, .cvs) { z-index: 2; }`;
  document.head.appendChild(st);
  let card = null, path = "", t = 0, gone = 0;
  const itemOf = c => { try { return view[+c.dataset.i]; } catch { return null; } };   // the page's list (v2.html)
  function place(c) {   // exactly over the card's picture, with its fit
    const img = c.querySelector("img"); if (!img) return false;
    const cs = getComputedStyle(img);
    Object.assign(v.style, { left: img.offsetLeft + "px", top: img.offsetTop + "px", width: img.offsetWidth + "px", height: img.offsetHeight + "px",
      objectFit: cs.objectFit, objectPosition: cs.objectPosition, borderRadius: cs.borderRadius });
    return true;
  }
  function start(c) {
    const it = itemOf(c); if (!it || it.kind !== "video" || !window.hyVideo) return;
    clearTimeout(gone); if (getComputedStyle(c).position === "static") c.style.position = "relative";
    if (!place(c)) return;
    card = c; c.appendChild(v); v.classList.remove("on");
    if (path !== it.path) { path = it.path; v.poster = ""; v.src = hyVideo.src(it.path, it, ""); }
    v.currentTime = 0; v.play().catch(() => {});
  }
  function stop() {
    clearTimeout(t); t = 0; if (!card) return;
    card = null; v.classList.remove("on"); v.pause();
    clearTimeout(gone); gone = setTimeout(() => { if (!card) v.remove(); }, FADE);
  }
  v.addEventListener("playing", () => { if (card) v.classList.add("on"); });
  v.addEventListener("error", () => { if (card && path && window.hyVideo && hyVideo.fallback(v, path, "")) v.play().catch(() => {}); });
  document.addEventListener("pointerover", e => {
    const c = e.target.closest && e.target.closest(".card[data-i]");
    if (c === card) return;
    if (!c) { if (card || t) stop(); return; }
    stop();
    const it = itemOf(c); if (!it || it.kind !== "video") return;
    if (window.hyVideo) hyVideo.prep(it.path);
    t = setTimeout(() => { t = 0; if (c.matches(":hover")) start(c); }, HOLD);
  }, { passive: true });
  document.addEventListener("pointerleave", stop);
  addEventListener("blur", stop);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  window.hyLibVideo = { el: v, stop };
})();
