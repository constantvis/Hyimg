// One row of the bell (owner 2026-10-03): its title, who it is from with his face and his agent's badge (ui/people.js hyWhoIn), when,
// its words and its pictures (ui/bellthumbs.js). The board's bell (canvas.html drawNtf) and Home's, which lists every board on this Mac
// (ui/homebell.js, owner 2026-10-08), draw the same row; its look is ui/bell.css. A classic script: Home loads no modules.
//   hyBellRow(n, o)   n: a row of GET /api/notifications; o.base: its board's server (Home is a file page, the pictures come from there),
//                     o.attrs: more attributes for the button, o.when: the time already in words, o.read: read or new (else the row's own read)
//   hyBellHead()      the panel's header: «Notifications» as a block's title (ui/hy/block.css); Home's bell keeps it
//   hyBellTabs        the board's bell header instead: All | Notifications | Comments with their counts, the «?» panel's control
//                     (<hy-segmented variant=pill>; owner 2026-10-10: «Почему ты не можешь сделать нотификации точно так же, как здесь? У нас
//                     будет первое все, второе только нотификации и третье будет только комментарии и таким образом можно будет фильтровать»).
//                     Comments are what people wrote: annotations, their replies and mentions, a reply to a note; the rest are notifications
//                     (an agent's or a person's work on the board). head(items) the header, rows(items) the rows of the chosen tab (the
//                     rows themselves as before: the owner keeps them as they are), on: the chosen tab, remembered for this viewer
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
  const kindOf = n => (n.kind === "comment" || n.kind === "note" ? "com" : "ntf");
  const TABS = [["all", "All"], ["ntf", "Notifications"], ["com", "Comments"]];
  window.hyBellTabs = {
    kindOf,
    get on() { let v = "all"; try { v = localStorage.getItem("cv.bellTab") || "all"; } catch {} return TABS.some(x => x[0] === v) ? v : "all"; },
    set on(v) { try { localStorage.setItem("cv.bellTab", v); } catch {} },
    rows(items) { const on = this.on; return on === "all" ? items : items.filter(n => kindOf(n) === on); },
    head(items) {
      const on = this.on, n = { all: items.length, ntf: items.filter(x => kindOf(x) === "ntf").length }; n.com = n.all - n.ntf;
      return `<div class="nh0 hy-bh nh-tabs"><hy-segmented class="ntabs" variant="pill" value="${on}" label="${esc(T("Show"))}">`
        + TABS.map(([k, w]) => `<button type="button" value="${k}" class="${k === on ? "on" : ""}"><span>${esc(T(w))}</span><em>${n[k]}</em></button>`).join("")
        + `</hy-segmented><span class="sp"></span><button type="button" class="nx" data-ntfx title="${esc(T("Close · Esc"))}" aria-label="${esc(T("Close"))}">`
        + `${window.hyIcon ? window.hyIcon("close", 13, 2) : "×"}</button></div>`;   // × as the «?» panel's (round 19's bell-tabs.html)
    },
  };
  // × closes the panel, as the bell does
  document.addEventListener("click", e => { if (e.target.closest && e.target.closest("#ntf [data-ntfx]")) { const b = document.getElementById("bntf"); if (b) b.click(); } });
  // a tab chosen: the list again (the board's drawNtf, canvas.html)
  document.addEventListener("hy-change", e => {
    const seg = e.target && e.target.closest && e.target.closest("#ntf .ntabs"); if (!seg || !e.detail) return;
    window.hyBellTabs.on = e.detail.value; if (typeof window.drawNtf === "function") window.drawNtf();
  });
})();
