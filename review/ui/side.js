// A side panel's parts (owner 2026-10-11, round 20's configurator r20/panels-config.html; DESIGN.md «Боковая панель»). One anatomy for the
// bell (the board's and Home's), «?», History, Settings at the side, the annotations' list and the Library beside the board; the look is
// ui/hy/side.css and its tokens ui/tokens.css --hy-side-*. A classic script: Home loads no modules.
//   hySide.head(o)            the header, 52 px. o.tabs: the panel's views as a pill (hySide.tabs), else o.title and o.count; o.acts: its
//                             buttons [[act, icon, words], ...], square 24 (<hy-icon-button size=s shape=square>), data-side-act=act;
//                             o.cls: more classes. No ×: Esc and the top row's round button close a panel (owner: «без крестика»)
//   hySide.tabs(items, on, o) <hy-segmented variant=pill> with items [[value, words, count?], ...], the chosen one on; o.cls, o.label
//   hySide.search(words, o)   the search field, 32 px, words its placeholder; o.cls, o.value
//   hySide.foot(html)         the footnote at the panel's foot (its words are the caller's, translated, with <b> for the key words)
//   hySide.none(words)        an empty list: its words in the middle, 14 px
(() => {
  if (window.hySide) return;
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const ic = (n, s, w = 2) => (window.hyIcon ? window.hyIcon(n, s, w) : "");
  const btn = ([act, icon, words]) => `<hy-icon-button class="hy-side-b" size="s" shape="square" variant="ghost" icon="${esc(icon)}" data-side-act="${esc(act)}"`
    + ` label="${esc(words)}" title="${esc(words)}"></hy-icon-button>`;
  const tabs = (items, on, o = {}) => `<hy-segmented class="${esc(o.cls || "")}" variant="pill" value="${esc(on)}"${o.label ? ` label="${esc(o.label)}"` : ""}>`
    + items.map(([v, words, n]) => `<button type="button" value="${esc(v)}" class="${v === on ? "on" : ""}"><span>${esc(words)}</span>`
      + `${n == null ? "" : `<em>${esc(n)}</em>`}</button>`).join("") + "</hy-segmented>";
  const head = (o = {}) => `<div class="hy-side-hd${o.cls ? " " + esc(o.cls) : ""}">`
    + (o.tabs || `<span class="hy-side-t">${esc(o.title || "")}${o.count == null ? "" : `<em>${esc(o.count)}</em>`}</span>`)
    + `<span class="hy-side-sp"></span>${(o.acts || []).map(btn).join("")}</div>`;
  const search = (words, o = {}) => `<label class="hy-side-q${o.cls ? " " + esc(o.cls) : ""}">${ic("search", 13)}<input type="search" placeholder="${esc(words)}"`
    + ` aria-label="${esc(words)}" value="${esc(o.value || "")}" autocomplete="off" spellcheck="false"></label>`;
  window.hySide = { head, tabs, search, btn, foot: html => `<div class="hy-side-ft">${html}</div>`, none: words => `<div class="hy-side-none">${esc(words)}</div>` };
})();
