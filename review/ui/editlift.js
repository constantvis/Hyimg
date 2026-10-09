// The card a mode edits, lifted off the board (owner 2026-10-08, about every editor mode: Dev, Image, 3D and any plugin's through
// ui/modes.js). Two requests:
//  «когда заходим в режим ... вот это выделение вокруг очень мешает видеть, что на гранях»: while a mode is open the board's selection
//   around that card is hidden, its outline (the board's .sel and the editors' own live outlines) and its corner squares; they come back on
//   leaving. The corners stay where they are, unseen, so the 3D studio's frame still resizes from them. The editor's own selection inside
//   the card (layers, elements) is the editor's. The card's note dots and the notes' arrows that end at it hide the same way (owner 2026-10-08 on an
//   HTML card: «она должна пропадать, когда мы нажимаем и входим в режим студии, и линия должна тоже пропадать»): the arrows' layer
//   (#links) lies over the cards, an arrow's end dot sat on the page being edited.
//  «Заметка поверх карточки в Studio ... заметка должна ложиться под карточки, когда мы открываем студию» (owner 2026-10-08): the card is on
//   top of every board thing while its Studio is open, only the Studio's own interface and the app's chrome stay over it. In the cards'
//   layer (#items: notes, headings, time lines, other cards) the card gets the highest z-index. The board's layers over #items are cut
//   where the card is, by one clip path in board units (#hyliftcut): the arrows (#links) and the drawings of other things (#annsvg g[data-o],
//   ui/annotate.js); the card's own drawings and comments are the Studio's and stay. A comment area of another thing gets the same cut in
//   its own units, a comment pin of another thing pointing at the card hides (it is 24 px on screen at any zoom, its units change with
//   the zoom). A group's title stuck to the top of the screen (#gsticky, screen units) is cut by the card's place on screen at each camera
//   frame. On leaving all of it is taken off, nothing else was changed.
//  «когда входишь в режим, у объекта, который обрабатываешь, появляется тень ... чтобы она плавно анимировалась»: the card gets a soft
//   elevation shadow that grows in as the camera settles and fades on leaving, and the rest of the board dims a little. It belongs to the
//   mode, not to the setting «Тени»: it shows with cv.shadow "0" too. Tokens in ui/tokens.css: --hy-sh-edit-near (a close ambient),
//   --hy-sh-edit-far (a far drop), --hy-edit-dim, --hy-edit-ms.
// How it stays cheap: one layer in the board's world (#hylift, over the cards and under the selection's bars) at the card's place in board
// units, so it moves with the camera for free. Its three children are drawn once (an outer box-shadow is never drawn under its own box, so
// the layer lies over the card without covering it) and only their opacity animates, on the compositor; the shadows keep their size on
// screen through --z like the board's other marks. Measured on a board of 50 cards: DESIGN.md «Режим поднимает объект».
//   const L = hyEditLift({ rect: id => {x, y, w, h} | null })   L.set(id | null, mode)   L.place()   L.id
(() => {
  if (window.hyEditLift) return;
  const css = `
#hylift { position: absolute; left: 0; top: 0; width: 0; height: 0; z-index: 3; pointer-events: none; visibility: hidden; }
#hylift.on, #hylift.out { visibility: visible; }
#hylift > i { position: absolute; inset: 0; opacity: 0; transition: opacity var(--hy-edit-ms, 420ms) var(--hy-ease, cubic-bezier(.32,.72,0,1)); }
#hylift:is(.on, .out) > i { will-change: opacity; }
#hylift > .near { box-shadow: var(--hy-sh-edit-near); transition-duration: calc(var(--hy-edit-ms, 420ms) * .6); }
#hylift > .far { box-shadow: var(--hy-sh-edit-far); }
#hylift > .dim { box-shadow: 0 0 0 30000px var(--hy-edit-dim); }   /* board units: a screen and more around the card from 10 % up; 4 000 000 cost frames */
#hylift.on > i { opacity: 1; }
#hylift.out > i { transition-duration: calc(var(--hy-edit-ms, 420ms) * .75); }
:root[data-hy-edit] #handles > :is(.selbox, .mbox, .h) { opacity: 0; }
:root[data-hy-edit] #cmpins > .cmpin.hylow { visibility: hidden; }
@media (prefers-reduced-motion: reduce) { #hylift > i { transition: none; } }`;
  window.hyEditLift = function (o = {}) {
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    // the card's own outline: a rule by its id, so it holds when the board makes the card's element anew (a picture turning into a frame)
    const own = document.createElement("style"); own.id = "hyliftcss"; document.head.appendChild(own);
    // the card's place cut out of the layers over it: one path, the board around and the card as a hole (evenodd), in board units
    const cut = document.createElementNS("http://www.w3.org/2000/svg", "svg"); cut.setAttribute("aria-hidden", "true");
    cut.setAttribute("style", "position: absolute; width: 0; height: 0; overflow: hidden; pointer-events: none");
    // hy-allow: icon-inline a clip path, not an icon: the board's layers over the card are cut by it
    cut.innerHTML = `<clipPath id="hyliftcut" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd"/></clipPath>`; document.body.appendChild(cut);
    const lift = document.createElement("div"); lift.id = "hylift"; lift.setAttribute("aria-hidden", "true");
    lift.innerHTML = `<i class="hy-lift dim"></i><i class="hy-lift far"></i><i class="hy-lift near"></i>`;
    const root = document.documentElement;
    let cur = null, box = "", rc = null, outT = 0, raf = 0;
    const B = 1e6;   // the board around the card, in board units: farther than any board reaches
    const ring = (x, y, w, h, u = "") => [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]].map(([a, b]) => `${+a.toFixed(2)}${u} ${+b.toFixed(2)}${u}`);
    const holed = (x, y, w, h, u) => `polygon(evenodd, ${[...ring(-B, -B, 2 * B, 2 * B, u), ...ring(x, y, w, h, u)].join(", ")})`;
    // the comments of other things over the card (ui/comments.js tags each pin and area with its object, data-o): an area cut in its own
    // units, a pin whose point lies on the card hidden
    function comments() {
      const el = document.getElementById("cmpins"); if (!el) return;
      for (const b of el.children) {
        const o = b.dataset.o, l = parseFloat(b.style.left), t = parseFloat(b.style.top), r = rc;
        const other = cur && r && o != null && o !== cur && Number.isFinite(l) && Number.isFinite(t);
        if (b.classList.contains("cmpin")) { b.classList.toggle("hylow", !!(other && l > r.x && l < r.x + r.w && t > r.y && t < r.y + r.h)); continue; }
        const w = parseFloat(b.style.width) || 0, h = parseFloat(b.style.height) || 0;
        const on = other && l < r.x + r.w && l + w > r.x && t < r.y + r.h && t + h > r.y, c = on ? holed(r.x - l, r.y - t, r.w, r.h, "px") : "";
        if (b._hycut !== c) { b.style.clipPath = c; b._hycut = c; }
      }
    }
    // a group's title stuck to the top of the screen: the card's place on screen cut out of that layer, at each camera frame
    function sticky() {
      const g = document.getElementById("gsticky"), C = typeof cam !== "undefined" ? cam : null; if (!g) return;
      const c = cur && rc && C && g.firstElementChild ? holed((rc.x - C.x) * C.z, (rc.y - C.y) * C.z, rc.w * C.z, rc.h * C.z, "px") : "";
      if (g._hycut !== c) { g.style.clipPath = c; g._hycut = c; }
    }
    if (typeof window.renderCam === "function") {
      const c0 = window.renderCam;
      window.renderCam = function (...a) { const out = c0.apply(this, a); if (cur) try { sticky(); } catch (e) { console.error(e); } return out; };
    }
    const ms = () => (parseFloat(getComputedStyle(root).getPropertyValue("--hy-edit-ms")) || 420);
    // in the world, right under the selection's bars (#handles): over the cards and a mode's own veil, under the bars over the card
    function home() {
      const w = document.getElementById("world"), h = document.getElementById("handles"); if (!w) return false;
      if (lift.parentNode !== w || (h && lift.nextSibling !== h)) w.insertBefore(lift, h && h.parentNode === w ? h : null);
      return true;
    }
    function place() {
      if (!cur || !home()) return;
      let r = null; try { r = o.rect && o.rect(cur); } catch (e) { console.error(e); }
      if (!r || !(r.w > 0) || !(r.h > 0)) return;
      const k = `${r.x}|${r.y}|${r.w}|${r.h}`;
      if (k !== box) {
        box = k; rc = { x: r.x, y: r.y, w: r.w, h: r.h };
        Object.assign(lift.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px" });
        cut.firstChild.firstChild.setAttribute("d", `M${ring(r.x - B, r.y - B, r.w + 2 * B, r.h + 2 * B).join("L")}ZM${ring(r.x, r.y, r.w, r.h).join("L")}Z`);
      }
      comments(); sticky();   // pins and stuck titles come and go with the board's render, which calls this through ui/modes.js
    }
    function set(id, mode) {
      id = id || null;
      if (id === cur) { if (id) { root.dataset.hyEdit = mode || "on"; place(); } return; }
      cancelAnimationFrame(raf); clearTimeout(outT);
      if (id) {
        cur = id; box = ""; root.dataset.hyEdit = mode || "on";
        const q = CSS.escape(id);
        own.textContent = `:root[data-hy-edit] #items [data-id="${q}"] { outline: none !important; }`
          // hy-allow: z-layer the card over the notes and headings in #items (its own stacking context, writing is from 1 000 000 up)
          + `:root[data-hy-edit] #items > [data-id="${q}"] { z-index: 2147483000 !important; }`
          + `:root[data-hy-edit] #items [data-id="${q}"] > .mk-note, :root[data-hy-edit] #links .arw[data-k$="|${q}"] { visibility: hidden; }`
          + `:root[data-hy-edit] :is(#links, #annsvg > g[data-o]:not([data-o="${q}"])) { clip-path: url(#hyliftcut); }`;
        place(); lift.classList.remove("out");
        // from nothing, one frame later: the shadow grows in while the camera brings the card in
        if (!lift.classList.contains("on")) raf = requestAnimationFrame(() => { raf = requestAnimationFrame(() => { if (cur === id) lift.classList.add("on"); }); });
        return;
      }
      cur = null; delete root.dataset.hyEdit; own.textContent = ""; rc = null; comments(); sticky();
      if (lift.classList.contains("on")) { lift.classList.replace("on", "out"); outT = setTimeout(() => lift.classList.remove("out"), ms() + 80); }
    }
    return { set, place, get id() { return cur; }, el: lift };
  };
})();
