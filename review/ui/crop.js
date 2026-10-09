// A picture cut to a square before it is kept (owner 2026-10-08: «Сделай так, чтобы аватар можно было менять»): a person's own picture
// (Settings › Profile, 256 px) and the badge of an agent kind (Settings › Profile › Agents, 96 px). A glass dialog like ui/confirm.js:
// the picture under a round window, a drag places it, the wheel or the slider zooms (100–800 %, around the pointer), a double click
// goes back to the whole picture; Save or Enter keeps it, Cancel, Esc or a press beside the dialog leaves everything as it was.
//   hyCrop(file, { size, title, max, type }) -> Promise<data URL | null>   (null: cancelled; rejected when the file is no picture)
// max: the longest data URL kept (people.py AVATAR_MAX), a JPEG's quality steps down until it fits; type "image/png" keeps transparency
// (a badge with a transparent mark), falling back to JPEG when too long. A classic script: people.js loads it the first time it is needed,
// on Home (a file page, no modules) as on a board.
(() => {
  if (window.hyCrop) return;
  const T = (k, v) => window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const VIEW = 240, ZMAX = 8;
  const CSS = `
#hyCrop { position: fixed; inset: 0; z-index: 99; display: grid; place-items: center; background: color-mix(in srgb, var(--panel) 30%, transparent);
  opacity: 0; transition: opacity .22s cubic-bezier(.32,.72,0,1); }
#hyCrop.on { opacity: 1; }
#hyCrop .hcr-box { width: 272px; box-sizing: border-box; padding: 14px 16px; display: grid; gap: 12px; border-radius: var(--hy-panel-r, 14px);
  border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 86%, transparent); -webkit-backdrop-filter: blur(18px) saturate(1.4);
  backdrop-filter: blur(18px) saturate(1.4); box-shadow: var(--plate-sh); color: var(--ink); font: 400 13px/1.4 var(--sans);
  transform: translateY(8px) scale(.98); transition: transform .26s cubic-bezier(.32,.72,0,1); }
#hyCrop.on .hcr-box { transform: none; }
#hyCrop .hcr-t { font-weight: 600; }
#hyCrop .hcr-stage { position: relative; width: ${VIEW}px; height: ${VIEW}px; overflow: hidden; border-radius: var(--hy-row-r, 8px); background: var(--raise);
  cursor: grab; touch-action: none; user-select: none; }
#hyCrop .hcr-stage.drag { cursor: grabbing; }
#hyCrop .hcr-stage img { position: absolute; left: 50%; top: 50%; max-width: none; pointer-events: none; transform-origin: 0 0; }
#hyCrop .hcr-ring { position: absolute; inset: 0; border-radius: 999px; pointer-events: none;
  box-shadow: 0 0 0 ${VIEW}px color-mix(in srgb, var(--panel) 62%, transparent), inset 0 0 0 1px color-mix(in srgb, var(--ink) 45%, transparent); }
#hyCrop .hy-hint { margin: -4px 0 0; }
#hyCrop .hcr-btns { display: flex; justify-content: flex-end; gap: 8px; }
#hyCrop .hcr-btns button { height: 28px; padding: 0 10px; border: 0; border-radius: var(--hy-row-r, 8px); background: var(--raise); box-shadow: inset 0 0 0 1px var(--line);
  color: var(--ink); font: 400 12.5px var(--sans); cursor: pointer; white-space: nowrap; }
#hyCrop .hcr-btns button:active { transform: scale(.97); }
#hyCrop .hcr-btns button.ok { background: var(--ink); color: var(--panel); box-shadow: none; font-weight: 600; }
#hyCrop .hcr-btns button.ok:hover { opacity: .88; }
@media (prefers-reduced-motion: reduce) { #hyCrop, #hyCrop .hcr-box { transition: none; } }`;

  function open(file) {
    return new Promise((ok, no) => {
      if (!file) { no(new Error("no file")); return; }
      const url = URL.createObjectURL(file), img = new Image();
      img.onload = () => ok({ img, url });
      img.onerror = () => { URL.revokeObjectURL(url); no(new Error("not a picture")); };
      img.src = url;
    });
  }
  // the window's square of the picture at n px: halved steps for a big picture, so a 4000 px photo does not alias into 256
  function cut(img, sx, sy, sw, n) {
    let src = img, x = sx, y = sy, w = sw;
    while (w / n > 2) {
      const h = Math.ceil(w / 2), c = document.createElement("canvas"); c.width = c.height = h;
      const g = c.getContext("2d"); g.imageSmoothingQuality = "high"; g.drawImage(src, x, y, w, w, 0, 0, h, h);
      src = c; x = 0; y = 0; w = h;
    }
    const c = document.createElement("canvas"); c.width = c.height = n;
    const g = c.getContext("2d"); g.imageSmoothingQuality = "high"; g.drawImage(src, x, y, w, w, 0, 0, n, n);
    return c;
  }
  function encode(c, type, max) {
    if (type === "image/png") { const d = c.toDataURL("image/png"); if (d.length <= max) return d; }
    const flat = document.createElement("canvas"); flat.width = c.width; flat.height = c.height;   // a JPEG has no transparency: on white
    const g = flat.getContext("2d"); g.fillStyle = "white"; g.fillRect(0, 0, c.width, c.height); g.drawImage(c, 0, 0);
    for (let q = .9; q >= .4; q -= .08) { const d = flat.toDataURL("image/jpeg", q); if (d.length <= max) return d; }
    return "";
  }

  window.hyCrop = (file, o = {}) => open(file).then(({ img, url }) => new Promise(done => {
    if (!document.getElementById("hyCropCss")) { const st = document.createElement("style"); st.id = "hyCropCss"; st.textContent = CSS; document.head.appendChild(st); }
    const W = img.naturalWidth, H = img.naturalHeight, fit = VIEW / Math.min(W, H);   // zoom 1: the shorter side fills the window
    let z = 1, x = 0, y = 0;   // the zoom, and the picture's centre from the window's centre in screen px
    const w = document.createElement("div"); w.id = "hyCrop"; w.setAttribute("role", "dialog"); w.setAttribute("aria-modal", "true");
    w.innerHTML = `<div class="hcr-box"><div class="hcr-t">${esc(o.title || T("Picture"))}</div>`
      + `<div class="hcr-stage" tabindex="0" aria-label="${esc(T("Drag to place, scroll to zoom"))}"><img alt="" draggable="false"><i class="hcr-ring"></i></div>`
      + `<div class="hcr-zoom"></div><div class="hy-hint">${esc(T("Drag to place, scroll to zoom"))}</div>`
      + `<div class="hcr-btns"><button type="button" data-a="no">${esc(T("Cancel"))}</button><button type="button" class="ok" data-a="ok">${esc(T("Save"))}</button></div></div>`;
    const stage = w.querySelector(".hcr-stage"), pic = w.querySelector("img"); pic.src = url;
    let slider = null;
    const clamp = () => {
      const mx = Math.max(0, (W * fit * z - VIEW) / 2), my = Math.max(0, (H * fit * z - VIEW) / 2);
      x = Math.min(mx, Math.max(-mx, x)); y = Math.min(my, Math.max(-my, y));
    };
    const draw = () => {
      clamp();
      const s = fit * z;
      pic.style.width = W + "px"; pic.style.height = H + "px";
      pic.style.transform = `translate(${x - W * s / 2}px, ${y - H * s / 2}px) scale(${s})`;
      if (slider && +slider.input.value !== Math.round(z * 100)) slider.set(Math.round(z * 100));
    };
    // a new zoom kept around a point of the window (px, py from its centre): what was under the pointer stays under it
    const zoom = (nz, px = 0, py = 0) => { nz = Math.min(ZMAX, Math.max(1, nz)); const r = nz / z; x = px - (px - x) * r; y = py - (py - y) * r; z = nz; draw(); };
    const zw = w.querySelector(".hcr-zoom");
    if (window.hySlider) {   // the app's one slider (ui/slider.js, Home and every board load it); without it the wheel still zooms
      slider = window.hySlider.create({ label: T("Zoom"), value: 100, min: 100, max: ZMAX * 100, step: 1, unit: "%", onInput: v => zoom(v / 100) });
      zw.appendChild(slider.el);
    }
    let grab = null;
    stage.addEventListener("pointerdown", e => { grab = { px: e.clientX, py: e.clientY, x, y }; stage.setPointerCapture(e.pointerId); stage.classList.add("drag"); });
    stage.addEventListener("pointermove", e => { if (!grab) return; x = grab.x + e.clientX - grab.px; y = grab.y + e.clientY - grab.py; draw(); });
    const drop = () => { grab = null; stage.classList.remove("drag"); };
    stage.addEventListener("pointerup", drop); stage.addEventListener("pointercancel", drop);
    stage.addEventListener("wheel", e => {
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      zoom(z * Math.exp(-e.deltaY * (e.ctrlKey ? .01 : .0025)), e.clientX - r.left - VIEW / 2, e.clientY - r.top - VIEW / 2);
    }, { passive: false });
    stage.addEventListener("dblclick", () => { z = 1; x = 0; y = 0; draw(); });
    let closed = false;
    const keys = e => {   // the dialog's keys only, before the page's (the settings panel closes on Esc too)
      e.stopImmediatePropagation();
      if (e.key === "Escape") { e.preventDefault(); close(false); } else if (e.key === "Enter") { e.preventDefault(); close(true); }
      else if (e.key.startsWith("Arrow") && e.target === stage) {
        e.preventDefault(); const d = e.shiftKey ? 20 : 4;
        x += e.key === "ArrowLeft" ? d : e.key === "ArrowRight" ? -d : 0; y += e.key === "ArrowUp" ? d : e.key === "ArrowDown" ? -d : 0; draw();
      }
    };
    function close(yes) {
      if (closed) return; closed = true; removeEventListener("keydown", keys, true);
      let out = null;
      if (yes) { const s = fit * z, sw = VIEW / s; out = encode(cut(img, W / 2 - x / s - sw / 2, H / 2 - y / s - sw / 2, sw, o.size || 256), o.type, o.max || 80000) || null; }
      URL.revokeObjectURL(url);
      w.classList.remove("on"); setTimeout(() => w.remove(), 220);
      done(out);
    }
    w.addEventListener("pointerdown", e => { e.stopPropagation(); if (e.target === w) close(false); });   // the settings panel stays open behind it
    w.addEventListener("click", e => { e.stopPropagation(); const b = e.target.closest("[data-a]"); if (b) close(b.dataset.a === "ok"); });
    addEventListener("keydown", keys, true);
    document.body.appendChild(w); draw();
    requestAnimationFrame(() => w.classList.add("on"));
    setTimeout(() => { if (!closed) w.querySelector("[data-a=ok]").focus(); }, 60);
  }));
})();
