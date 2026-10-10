// The pins of annotations inside a Studio, one look for all of them and for the board's (owner 2026-10-09 on round 15: «3D у нас,
// естественно, тоже не хватает аннотаций ... Image Studio точно так же, чтобы я мог выбрать и слой»). A thread tied to a layer of an Image
// Studio frame or to an object of a 3D scene (anchor.part, review/comments.py clean_part) shows on the work as Hyimg's one annotation pin
// (ui/hy/apin.css, owner 2026-10-10: «круг с уголком внизу слева»): its sharp bottom left corner stands on the spot, the count of its
// messages on the Studio's colour (--sel inside a Studio, ui/modes.js); its area a dashed outline of the same colour. The thread itself is
// the board's (ui/comments.js): a click on a pin opens it. The Studio says where each pin points in its own pixels; this module only draws
// and reports clicks. A press on a pin or a count does not close the open thread (data-cm-keep, ui/comments.js), its click decides.
// Words typed and left unsent stay visible (P4 S-32, П4 audit 2026-10-10: inside a Studio they looked lost): kept, a dot on the pin (a
// thread with a reply not sent; a new annotation not sent: draft and kept, a click opens it again), as the board's pins have.
//   const P = hyStudioPins.layer(host, { onPin(id, ev), z })   P.draw([{ id, x, y, n, title, on, draft, kept, area: {x, y, w, h} }])   P.destroy()
//   hyStudioPins.count(n, title)   the count of open annotations on a layer's row: the pin, compact (.hy-apin.s), no bigger than the row's
//                                  lock and eye (owner 2026-10-10: «очень крупные ... просто меньше размер»); a click opens them
(() => {
  if (window.hyStudioPins) return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const STYLE = `
    .hy-spins { position: absolute; left: 0; top: 0; right: 0; bottom: 0; pointer-events: none; overflow: hidden; }
    .hy-spins.fixed { position: fixed; }
    .hy-sarea { position: absolute; box-sizing: border-box; border: 1.5px dashed var(--hy-studio, var(--sel)); border-radius: 4px; pointer-events: none; }
    .hy-sarea.on { border-style: solid; background: color-mix(in srgb, var(--hy-studio, var(--sel)) 12%, transparent); }
    .hy-ann-n { margin-left: 6px; align-self: center; }`;
  // the pin's own look is one file (ui/hy/apin.css), the board's too (annotate.css imports it); a page without it (Image Studio's) gets
  // it here. Resolves once the pins are drawn by it: until then the layer stays hidden, no pin flashes unstyled where it does not point
  function style(doc) {
    if (!doc.getElementById("hy-spins-css")) { const s = doc.createElement("style"); s.id = "hy-spins-css"; s.textContent = STYLE; doc.head.appendChild(s); }
    const has = () => { const p = doc.createElement("i"); p.className = "hy-apin"; p.style.visibility = "hidden"; doc.body.appendChild(p);
      const ok = doc.defaultView.getComputedStyle(p).borderBottomLeftRadius === "3px"; p.remove(); return ok; };
    if (has()) return Promise.resolve();
    let l = doc.querySelector('link[href="/ui/hy/apin.css"]');
    if (!l) { l = doc.createElement("link"); l.rel = "stylesheet"; l.href = "/ui/hy/apin.css"; doc.head.appendChild(l); }
    return new Promise(ok => { let n = 0; const t = () => (has() || ++n > 100 ? ok() : setTimeout(t, 30)); l.addEventListener("load", t, { once: true }); setTimeout(t, 30); });
  }
  function layer(host, o = {}) {
    const doc = host.ownerDocument, ready = style(doc);
    const el = doc.createElement("div"); el.className = "hy-spins" + (o.fixed ? " fixed" : ""); if (o.z != null) el.style.zIndex = String(o.z);
    el.dataset.hyStudioPins = ""; host.appendChild(el); el.style.visibility = "hidden"; ready.then(() => { el.style.visibility = ""; });
    // a press on a pin is the pin's: nothing under it (the Studio's tool, the board) hears it
    el.addEventListener("pointerdown", e => { const b = e.target.closest(".hy-spin"); if (!b) return; e.stopPropagation(); e.preventDefault(); });
    el.addEventListener("click", e => { const b = e.target.closest(".hy-spin"); if (!b || b.dataset.c === "draft") return; e.stopPropagation(); if (o.onPin) o.onPin(b.dataset.c, e); });
    let sig = "";
    function draw(items) {
      const s = JSON.stringify(items || []); if (s === sig) return; sig = s;
      const want = new Map((items || []).map(x => [x.id, x]));
      for (const n of [...el.children]) if (!want.has(n.dataset.c) || (n.classList.contains("hy-sarea") && !want.get(n.dataset.c).area)) n.remove();
      for (const x of want.values()) {
        if (x.area) {
          let a = el.querySelector(`:scope > .hy-sarea[data-c="${CSS.escape(x.id)}"]`);
          if (!a) { a = doc.createElement("div"); a.className = "hy-sarea"; a.dataset.c = x.id; el.prepend(a); }
          Object.assign(a.style, { left: x.area.x + "px", top: x.area.y + "px", width: Math.max(1, x.area.w) + "px", height: Math.max(1, x.area.h) + "px" });
          a.classList.toggle("on", !!(x.on || x.draft));
        }
        if (x.x == null || x.y == null) continue;
        let b = el.querySelector(`:scope > .hy-spin[data-c="${CSS.escape(x.id)}"]`);
        if (!b) { b = doc.createElement("button"); b.type = "button"; b.className = "hy-spin hy-apin"; b.dataset.c = x.id; b.dataset.cmKeep = ""; el.appendChild(b); }
        const n = x.draft ? "+" : String(x.n ?? "");
        if (b.textContent !== n || !!b.querySelector(".hy-apin-d") !== !!x.kept) { b.textContent = n; if (x.kept) b.insertAdjacentHTML("beforeend", '<i class="hy-apin-d"></i>'); }
        b.title = x.title || ""; b.setAttribute("aria-label", x.title || n);
        b.style.left = Math.round(x.x) + "px"; b.style.top = Math.round(x.y) + "px";
        b.classList.toggle("on", !!x.on); b.classList.toggle("draft", !!x.draft);
      }
    }
    return { el, draw, clear: () => draw([]), destroy() { el.remove(); } };
  }
  const count = (n, title) => (n > 0 ? `<button type="button" class="hy-ann-n hy-apin s" count="${n}" data-ann-n data-cm-keep title="${esc(title || "")}"`
    + ` aria-label="${esc(title || String(n))}">${n}</button>` : "");
  window.hyStudioPins = { layer, count, css: STYLE };
})();
