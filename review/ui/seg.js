// One choice component app-wide (owner 2026-10-06: «why isn't this a switch like ours», about Home's cards/list switch; the rule «one
// system: one choice component, one selected state»). A .seg is one capsule of options; the chosen one sits on a thumb that slides
// under it, eased, as in the frame editor's Seg. Pages keep marking the chosen button with aria-pressed="true" (or the class "on");
// this file adds the thumb (<i class="st">) and moves it whenever that mark changes, the seg changes size or comes into view. The look
// is ui/look.css (.seg). A .seg.updown is a pair of buttons, not a choice: it gets no thumb. [data-seg] is a choice laid out its own
// way (a grid, the library's verdicts) that takes the thumb without the capsule's layout; a [data-toggle] button in it is not a choice.
//   hySeg(root)   gives every .seg under root (and root itself) its thumb, once each; a page calls it after it draws new segs
(() => {
  if (window.hySeg) return;
  // loaded by a <script> it gives every .seg of the page its thumb by itself; loaded by ui/hy/segmented.js (which sets HY_SEG_MANUAL first)
  // it only defines hySeg, so a page with .seg of its own (the image studio's Seg) is not touched
  const auto = !window.HY_SEG_MANUAL;
  const chosen = seg => [...seg.children].find(b => b.tagName === "BUTTON" && !b.hasAttribute("data-toggle") && (b.getAttribute("aria-pressed") === "true" || b.classList.contains("on")));
  // now: no slide (the first placement, a resize, a seg that just came into view); else it slides to the new choice
  function place(seg, now) {
    const th = seg._st, b = chosen(seg); if (!th) return;
    if (!b || !b.offsetWidth) { if (!b) th.classList.remove("now"); th.style.opacity = "0"; return; }   // nothing chosen: it fades out
    const hidden = th.style.opacity === "0";
    if (now || hidden) th.classList.add("now");
    Object.assign(th.style, { width: b.offsetWidth + "px", height: b.offsetHeight + "px", transform: `translate(${b.offsetLeft}px, ${b.offsetTop}px)` });
    th.getBoundingClientRect();
    if (hidden && !now) { th.classList.remove("now"); th.style.opacity = "1"; return; }   // the first choice: it fades in where it is
    th.style.opacity = "1";
    if (th.classList.contains("now")) requestAnimationFrame(() => th.classList.remove("now"));
  }
  function init(seg) {
    if (seg._st || seg.classList.contains("updown")) return;
    const th = document.createElement("i"); th.className = "st now"; th.setAttribute("aria-hidden", "true"); th.style.opacity = "0";
    seg.prepend(th); seg._st = th; seg.classList.add("has-st");
    new MutationObserver(ms => { if (ms.some(m => m.target !== th)) place(seg); }).observe(seg, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-pressed", "class"] });
    new ResizeObserver(() => place(seg, true)).observe(seg);
    place(seg, true);
  }
  window.hySeg = (root = document) => {
    if (root.matches && root.matches(".seg, [data-seg]")) init(root);
    root.querySelectorAll(".seg, [data-seg]").forEach(init);
  };
  if (!auto) return;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => window.hySeg()); else window.hySeg();
})();
