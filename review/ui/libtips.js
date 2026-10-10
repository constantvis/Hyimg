// The library's tip (ui/hy/tip.js, round 12's version 9, owner 2026-10-09 on r12/docs-tips.html: «9 версия идеальна — делай»): one line in
// the library's header after the folder's path, as round 10 had it («⌥-click a tag hides it»: «Идея просто гениальна»). One tip each time
// the library opens, a click for the next, × on hover closes them; filtering the long way (click, click again to exclude) shows the quick
// way once (v2.html fcycle calls hyTip.way). The tip takes only the header's free part: it ends in an ellipsis, and with less room than
// MIN it is not there at all. Only what the library really does.
(() => {
  const MIN = 72, GAP = 10;   // the bulb and two words at least, 10 px from the words and the next control
  const TIPS = [
    { id: "altx", t: "<b>⌥-click</b> a filter excludes it at once", auto: false },   // v2.html fcycle(id, alt)
    { id: "folder", t: "<b>Drag a folder</b> onto the board: it lands as a block", auto: false },   // a folder row is draggable
    { id: "ctab", t: "<b>⌃Tab</b> returns to the board you had before", keys: ["ctrl+tab"] },   // ui/switcher.js
  ];
  // ⌃Tab is the app's (P4 B-54): in a browser it goes to the browser's next tab, so the tip is not there; in the app the page never sees
  // the key (the app takes it first), its cards (ui/switcher.js) mark it learned
  const app = (() => { try { return !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.hyimg) || /HyimgCEF/.test(navigator.userAgent); } catch { return false; } })();
  if (!app) TIPS.splice(TIPS.findIndex(t => t.id === "ctab"), 1);
  const wrap = document.createElement("span"); wrap.className = "libtip";
  wrap.style.cssText = "position:absolute;top:0;bottom:0;display:none;align-items:center;min-width:0;pointer-events:none";
  let raf = 0;
  // the free part of the header: from the end of the path's words to the next control, the header's own padding kept
  const fit = () => {
    raf = 0;
    const bar = document.getElementById("fbar"), path = bar && bar.querySelector(".fpath"); if (!bar || !path) return;
    if (wrap.parentElement !== bar) bar.append(wrap);   // the header is rebuilt from a string (renderFolders): back in it
    const b = bar.getBoundingClientRect(), cs = getComputedStyle(bar);
    let end = path.getBoundingClientRect().left, next = b.right - (parseFloat(cs.paddingRight) || 0);
    for (const c of path.children) if (c.getClientRects().length) end = Math.max(end, c.getBoundingClientRect().right);
    let after = false;
    for (const c of bar.children) {
      if (c === path) { after = true; continue; }
      if (after && c !== wrap && c.getClientRects().length && c.getBoundingClientRect().width) next = Math.min(next, c.getBoundingClientRect().left);
    }
    const free = next - end - GAP * 2, on = free >= MIN && b.width > 0;
    wrap.style.display = on ? "flex" : "none";
    if (on) { wrap.style.left = Math.round(end + GAP - b.left) + "px"; wrap.style.width = Math.floor(free) + "px"; }
  };
  const soon = () => { if (!raf) raf = requestAnimationFrame(fit); };
  const start = () => {
    const bar = document.getElementById("fbar"); if (!bar || !window.hyTip) return;
    new ResizeObserver(soon).observe(bar);
    new MutationObserver(soon).observe(bar, { childList: true, subtree: true, characterData: true });
    fit(); window.hyTip.show(wrap, "library", TIPS);   // a visit: the library opened
  };
  customElements.whenDefined("hy-tip").then(() => (document.readyState === "loading" ? addEventListener("DOMContentLoaded", start, { once: true }) : start()));
  // a folder dragged out of the library is the quick way of both tips that teach it (the board's empty page has it too, ui/boardhints.js)
  document.addEventListener("dragstart", e => {
    if (!(e.target instanceof Element) || !e.target.closest(".frow[data-f]") || !window.hyTip) return;
    window.hyTip.used("library", "folder"); window.hyTip.used("board", "folder");
  }, true);
})();
