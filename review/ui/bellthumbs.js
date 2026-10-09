// The bell's pictures (owner 2026-10-08: «Расстраивает, что нет картинок ... Желательно показать либо пространство, либо прям этот
// объект, который выделен»). Each row of the bell carries its tiles from the server (review/feedthumbs.py, "pv" and "pvn"): a
// picture's thumbnail (square), or a crop of the commented area, a card's still, the board around a pin (3:2). This file draws them
// under the row's text: four at most, then «+N»; every tile has its size before its picture comes (no jump), the pictures load lazily.
// The mark (the area's outline, the pin's dot) is drawn here over the tile, in the colour of the comment's author.
(() => {
  if (window.hyBellThumbs) return;
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const enc = encodeURIComponent;
  const theme = () => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const colorOf = who => {   // a person's colour (people.js), the mark's
    const P = (window.hyPeople && hyPeople.people && hyPeople.people()) || {};
    return (window.HY_COLORS || {})[(P[who] || {}).color] || "";
  };
  const pct = v => `${Math.round(v * 1000) / 10}%`;

  const css = document.createElement("style");
  css.textContent = `
#ntf .nt .pv { display: flex; gap: 4px; margin-top: 2px; }
#ntf .nt .pv .bt { position: relative; flex: none; width: 48px; height: 48px; border-radius: 6px; overflow: hidden; background: var(--raise); }
#ntf .nt .pv .bt.w { width: 72px; }
#ntf .nt .pv .bt.l { width: 144px; height: 96px; border-radius: 8px; }
#ntf .nt .pv .bt img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; border-radius: 0; background: none; }
#ntf .nt .pv .bt.w img, #ntf .nt .pv .bt.l img { object-fit: fill; }
#ntf .nt .pv .bt .ma { position: absolute; box-sizing: border-box; border: 2px solid var(--c, var(--sel)); border-radius: 3px;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--bg) 55%, transparent); pointer-events: none; }
#ntf .nt .pv .bt .mp { position: absolute; width: 8px; height: 8px; margin: -4px 0 0 -4px; border-radius: 999px; background: var(--c, var(--sel));
  box-shadow: 0 0 0 2px var(--panel); pointer-events: none; }
#ntf .nt .pv .bmore { flex: none; display: grid; place-items: center; min-width: 32px; height: 48px; padding: 0 6px; box-sizing: border-box;
  border-radius: 6px; background: var(--raise); color: var(--sub); font-size: 11px; font-weight: 600; }`;
  document.head.appendChild(css);

  function mark(d) {
    const m = d.mark; if (!m) return "";
    const c = colorOf(d.who), st = c ? `--c:${c};` : "";
    if (m.r) return `<i class="ma" style="${st}left:${pct(m.r[0])};top:${pct(m.r[1])};width:${pct(m.r[2])};height:${pct(m.r[3])}"></i>`;
    if (m.pin) return `<i class="mp" style="${st}left:${pct(m.pin[0])};top:${pct(m.pin[1])}"></i>`;
    return "";
  }
  function tile(d, large, base) {
    const wide = d.k === "crop" || d.k === "region", src = (/^\/(?!\/)/.test(d.src || "") ? base : "") + d.src + (d.k === "region" ? `&th=${theme()}` : "");
    return `<span class="bt${wide ? (large ? " l" : " w") : ""}" data-k="${esc(d.k)}"><img alt="" loading="lazy" decoding="async" draggable="false"`
      + ` src="${esc(src)}" onerror="this.style.visibility='hidden'">${mark(d)}</span>`;
  }
  // the strip of one row: its tiles, or (a server not restarted yet) the pictures it named; base: the board's server when the page is not
  // (Home, a file page, lists every board's bell: ui/homebell.js)
  window.hyBellThumbs = (n, base = "") => {
    const L = Array.isArray(n.pv) ? n.pv : (n.previews || []).map(p => ({ src: `/thumb?p=${enc(p)}&s=320`, k: "pic" }));
    if (!L.length) return "";
    const shown = L.slice(0, 4), more = Math.max(0, (n.pvn || L.length) - shown.length);
    const large = shown.length === 1 && shown[0].k !== "pic";   // one crop alone: large enough to read
    return `<span class="pv">${shown.map(d => tile(d, large, base)).join("")}${more ? `<span class="bmore">+${more}</span>` : ""}</span>`;
  };
})();
