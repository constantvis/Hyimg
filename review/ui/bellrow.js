// One row of the bell (owner 2026-10-03): its title, who it is from with his face and his agent's badge (ui/people.js hyWhoIn), when,
// its words and its pictures (ui/bellthumbs.js). The board's bell (canvas.html drawNtf) and Home's, which lists every board on this Mac
// (ui/homebell.js, owner 2026-10-08), draw the same row; its look is ui/bell.css. A classic script: Home loads no modules.
//   hyBellRow(n, o)   n: a row of GET /api/notifications; o.base: its board's server (Home is a file page, the pictures come from there),
//                     o.attrs: more attributes for the button, o.when: the time already in words, o.read: read or new (else the row's own read)
//   hyBellHead()      Home's header: «Notifications» as a side panel's title (ui/side.js, round 20: 52 px, as the board's)
//   hyBellBody(rows, none, foot)  the list under a header: the rows, or none in the middle when there are none, then the footnote
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
  // the panel's header and list, the board's and Home's: a side panel's (ui/side.js, owner 2026-10-11, round 20: «Шапка 52, вкладки в шапке
  // · без крестика · Подвал сноска у всех · Пустой список по центру 14»); before it Home's was a block's one title, round 12
  window.hyBellHead = () => window.hySide.head({ title: T("Notifications") });
  window.hyBellBody = (rows, none, foot) => `<div class="hy-side-body nl">${rows || window.hySide.none(none)}</div>${window.hySide.foot(foot)}`;
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
    head(items) {   // no × since round 20 (2026-10-11): Esc and the bell itself close it (round 19's bell-tabs.html had a round ×)
      const on = this.on, n = { all: items.length, ntf: items.filter(x => kindOf(x) === "ntf").length }; n.com = n.all - n.ntf;
      return window.hySide.head({ tabs: window.hySide.tabs(TABS.map(([k, w]) => [k, T(w), n[k]]), on, { cls: "ntabs", label: T("Show") }) });
    },
    // the whole panel: the header, the chosen tab's rows (html, written by the page) or «Nothing yet», the footnote
    panel(items, rows) { return this.head(items) + window.hyBellBody(rows, T("Nothing yet"), T("Agents' work and comments · <b>Esc</b> closes")); },
  };
  // a tab chosen: the list again (the board's drawNtf, canvas.html)
  document.addEventListener("hy-change", e => {
    const seg = e.target && e.target.closest && e.target.closest("#ntf .ntabs"); if (!seg || !e.detail) return;
    window.hyBellTabs.on = e.detail.value; if (typeof window.drawNtf === "function") window.drawNtf();
  });
})();
