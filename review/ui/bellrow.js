// One row of the bell (owner 2026-10-03): its title, who it is from with his face and his agent's badge (ui/people.js hyWhoIn), when,
// its words and its pictures (ui/bellthumbs.js). The board's bell (canvas.html drawNtf) and Home's, which lists every board on this Mac
// (ui/homebell.js, owner 2026-10-08), draw the same row; its look is ui/bell.css. A classic script: Home loads no modules.
//   hyBellRow(n, o)   n: a row of GET /api/notifications; o.base: its board's server (Home is a file page, the pictures come from there),
//                     o.attrs: more attributes for the button, o.when: the time already in words, o.read: read or new (else the row's own read)
//   hyBellHead()      the panel's header: «Notifications» as a block's title (ui/hy/block.css)
//   hyBellAgo(t)      «just now», «5 min ago», «3 h ago», then «10.08 14:05», from a row's t («YYYY-MM-DD HH:MM:SS», local time) or
//                     unix seconds (Home's news, ui/homebell.js)
(() => {
  if (window.hyBellRow) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const two = v => String(v).padStart(2, "0");
  const ago = t => {
    const num = typeof t === "number", d = num ? new Date(t * 1000) : new Date(String(t || "").replace(" ", "T")), m = Math.round((Date.now() - d.getTime()) / 60000);
    if (m < 1) return T("just now"); if (m < 60) return T("{n} min ago", { n: m }); if (m < 1440) return T("{n} h ago", { n: Math.round(m / 60) });
    if (!num) return String(t || "").slice(5, 16).replace("-", ".");
    return isNaN(d) ? "" : `${two(d.getMonth() + 1)}.${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}`;
  };
  // the panel's header, the board's and Home's (round 12 «A · Line», owner 2026-10-09): the block's one title on its plate, ui/hy/block.css
  window.hyBellHead = () => `<div class="nh0 hy-bh"><span class="hy-bh-tab hy-bh-title on">${window.hyIcon ? window.hyIcon("notifications", 14, 1.85) : ""}`
    + `${esc(T("Notifications"))}</span></div>`;
  window.hyBellRow = (n, o = {}) => `<button class="nt${(typeof o.read === "boolean" ? o.read : n.read) ? "" : " new"}" data-n="${esc(n.id)}"${o.attrs || ""}><b>${esc(n.title)}</b>`
    + `<span class="who">${(window.hyWhoIn && window.hyWhoIn(n)) || esc(n.who)} · ${o.when || ago(n.t)}</span>${n.text ? `<p>${esc(n.text)}</p>` : ""}`
    + `${(window.hyBellThumbs && window.hyBellThumbs(n, o.base)) || ""}</button>`;
  window.hyBellAgo = ago;
})();
