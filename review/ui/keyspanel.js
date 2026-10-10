// The ? panel (the top row's ?, canvas.html #keys), round 15's Tips (owner 2026-10-09, ♥ on Concepts/html/editors-concepts/r15/r15-tips.html,
// version 1, the list; before that, on round 14's Tips: «Почему здесь у нас нет иконок этих кнопок? И у нас же есть шорткат-символы»).
// The board's dark side panel, 340 px as History; its header as r15 draws it (58 px, a pill of two tabs, no icons: <hy-segmented
// variant=pill>, the bell's tabs too), not the blocks' standard 24 px tabs of round 14 (owner 2026-10-10: round 15 wins where they differ). Two tabs:
//   Tips      «Here · Board»: a few things to do here, each with its icon and its keys; «Keys here»: the main keys, a row each
//   All keys  every row canvas.html writes, and those other modules add later (ui/anncore.js C, ui/arrange.js after ⌥D, ui/annotate.js P)
// Every row is the action's icon (the menus' and the dock's, ui/icons.js HY_IC), its words, its keys at the right end, one cap per key
// (<kbd> and <hy-kbd>, ui/hy/kbd.css). A gesture's row (a drag, a double click) has its words in front instead of caps. A row is found by its
// keys, which do not change with the language, or by its words in the page's language. The look: ui/keyspanel.css.
(() => {
  if (window.hyKeysPanel) return;
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/ui/keyspanel.css";
  (document.head || document.documentElement).appendChild(css);
  const t = (s, o) => (window.T ? window.T(s, o) : s);
  const ICON = { "N": "note", "C": "comment", "P": "pen", "⌘M": "library", "⌘.": "eyeoff", "⌘G": "group", "⇧⌘G": "ungroup", "⌘]⌘[": "orderForward",
    "⌥⌘]⌥⌘[": "orderFront", "⇧C": "crop", "⌘C⌘X": "copy", "⌘V": "paste", "⌘D": "duplicate", "⌥A": "tidyBlock", "⌥S": "tidyRow", "⌥D": "tidy", "⌫": "trash",
    "⌘Z⇧⌘Z": "undo", "⌘A": "select", "Esc": "close", "↵": "open", "F": "heart", "L": "timeline", "190": "opacity", "⌥P": "split", "⇧⌘C": "image",
    "⌘F": "search", "\\": "library", "X⌘Z": "crop", "⇧1": "fit", "⌘X⌘V": "toPage", "←↑→↓": "move", "↵Esc": "check", "R": "frame", "⌘B⌘I": "editText", "Space": "hand", "⌘": "zoomIn", "⌥": "copy" };
  ICON["⌥↑⌥↓"] = "library";   // the library's collection above, below (round 18)
  // a row without keys of its own, by its first words (English, as canvas.html writes them; compared in the page's language)
  const WORDS = { "drag": "library", "scroll wheel, trackpad": "hand", "marquee,": "select", "double-click on empty space": "heading",
    "a note over frames": "link", "a note inside a group, linked to nothing": "group", "the note's yellow dot": "drawArrow", "small and big": "editText",
    "colored dots above a note": "palette", "“Area” above a note": "marquee", "in a note": "note", "double-click": "image", "⤢ in a video's pill": "expand",
    "pointer over a video": "play", "▶ in the video's corner,": "play", "the line at the bottom of a video": "play", "corner or edge": "resize", "pages": "board",
    "right click › Arrange": "gridMake", "⌘ while dragging": "guide", "Arrange › Layout patterns": "layouts", "on the bar": "layouts" };
  // round 15's two lists: what to do here, the main keys (the keys and the icons are the code's: canvas.html, ui/anncore.js, ui/arrange.js)
  const TIPS = [["copy", "<kbd>⌥</kbd> drag a picture: a copy"], ["image", "<b>Double click</b> an image: Image Studio"],
    ["note", "<kbd>N</kbd> drops a note under the pointer, type at once"], ["tidyBlock", "<kbd>⌥</kbd><kbd>A</kbd> lays the picked pictures out as a block"],
    ["library", "<b>Drag a folder</b> from the Library: it lands as a block"]];
  const KEYS = [["note", "Note", "N"], ["comment", "Annotation", "C"], ["group", "Group", "⌘G"], ["tidyBlock", "Arrange as a block", "⌥A"],
    ["fit", "Show all", "⇧1"], ["library", "Library", "⌘M"], ["eyeoff", "Hide the interface", "⌘."], ["undo", "Undo", "⌘Z"], ["redo", "Redo", "⇧⌘Z"]];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const svg = n => (n && window.HY_IC ? window.HY_IC[n] || "" : "");
  const caps = (keys, size) => [...keys].map(k => `<hy-kbd${size ? ` size="${size}"` : ""}>${esc(k)}</hy-kbd>`).join("");
  const keysOf = row => [...(row.querySelector(".k")?.querySelectorAll("kbd") || [])].map(k => k.textContent.trim()).join("");
  let P = null;   // the panel's parts once built

  function iconOf(row) {
    if (row.hasAttribute("data-arrange-keys")) {
      if (row.querySelector(".k svg")) return "";   // the row that draws its button itself
      const i = [...row.parentElement.querySelectorAll("[data-arrange-keys]")].indexOf(row);
      return ["gridMake", "layouts"][i] || "";
    }
    const head = (row.querySelector(".k")?.textContent || "").trim();
    for (const [w, n] of Object.entries(WORDS)) if (head === t(w) || head.startsWith(t(w))) return n;
    const k = keysOf(row); return ICON[k] || ICON[k.replace(t("Space"), "Space")] || "";   // a key's name is in the page's language
  }
  // a row canvas.html (or a module) writes, <div><span class="k">keys</span> words</div>: its icon in front, its words in their own span
  function dress(row) {
    if (row.tagName !== "DIV" || !row.querySelector(":scope > .k") || row.classList.contains("kp-row")) return;
    row.classList.add("kp-row", "kp-leg");
    const k = row.querySelector(":scope > .k"), w = document.createElement("span"); w.className = "t";
    while (k.nextSibling) w.appendChild(k.nextSibling);
    row.append(w);
    if (!k.querySelector("kbd")) row.classList.add("kp-gest");
    const name = iconOf(row), i = document.createElement("span");
    i.className = "kpi"; i.setAttribute("aria-hidden", "true"); if (name) i.dataset.icon = name; i.innerHTML = svg(name);
    row.prepend(i);
  }

  function build(panel) {
    const legacy = [...panel.children].filter(r => r.tagName === "DIV" && r.querySelector(":scope > .k"));
    // the tabs: <hy-segmented variant=pill>, the same control as the bell's All | Notifications | Comments (owner 2026-10-10)
    panel.innerHTML = `<div class="kp-in"><div class="kp-bh"><hy-segmented class="kp-tabs" variant="pill" value="tips">
        <button type="button" class="kp-tab on" value="tips" role="tab" aria-selected="true" data-kt="tips"><span></span></button>
        <button type="button" class="kp-tab" value="all" role="tab" aria-selected="false" data-kt="all"><span></span><em></em></button></hy-segmented>
        <span class="sp"></span><button type="button" class="kp-x">${svg("close")}</button></div>
      <label class="kp-s">${svg("search")}<input type="search" autocomplete="off" spellcheck="false"></label>
      <div class="kp-body"><section data-kt="tips"><div class="kp-lb" data-l="here"><span></span><em></em></div><div class="kp-tips"></div>
        <div class="kp-lb" data-l="keys"><span></span><em></em><span class="sp"></span><button type="button" class="kp-lnk" data-kt="all"></button></div><div class="kp-rows kp-main"></div></section>
        <section data-kt="all" hidden><div class="kp-rows kp-all"></div></section><div class="kp-none" hidden></div></div></div>`;
    const $ = s => panel.querySelector(s);
    P = { panel, all: $(".kp-all"), main: $(".kp-main"), tips: $(".kp-tips"), q: $(".kp-s input"), none: $(".kp-none") };
    $('[data-kt="tips"].kp-tab span').textContent = t("Tips"); $('[data-kt="all"].kp-tab span').textContent = t("All keys");
    const x = $(".kp-x"); x.title = t("Close · Esc"); x.setAttribute("aria-label", t("Close"));
    P.q.placeholder = t("Search tips and keys"); P.q.setAttribute("aria-label", t("Search tips and keys"));
    $('[data-l="here"] span').textContent = t("Here · Board"); $('[data-l="here"] em').textContent = TIPS.length;
    $('[data-l="keys"] span').textContent = t("Keys here"); $('[data-l="keys"] em').textContent = KEYS.length;
    P.tips.innerHTML = TIPS.map(([ic, h]) => `<div class="kp-tip"><span class="kpi" data-icon="${ic}" aria-hidden="true">${svg(ic)}</span>`
      + `<span>${t(h).replace(/<kbd>(.*?)<\/kbd>/g, (_, k) => caps(k, "m"))}</span></div>`).join("");
    P.main.innerHTML = KEYS.map(([ic, w, k]) => `<div class="kp-row"><span class="kpi" data-icon="${ic}" aria-hidden="true">${svg(ic)}</span>`
      + `<span class="t">${esc(t(w))}</span><span class="k">${caps(k)}</span></div>`).join("");
    legacy.forEach(r => { P.all.append(r); dress(r); });
    count();
    panel.addEventListener("click", e => {
      const tab = e.target.closest("[data-kt]"); if (tab && tab.tagName === "BUTTON") { show(tab.dataset.kt); return; }
      if (e.target.closest(".kp-x")) { const b = document.getElementById("bkeys"); if (b) b.click(); }
    });
    P.q.addEventListener("input", filter);
    // Esc in the search: its words first, then the panel closes (P4 B-16, the board's one Esc order)
    P.q.addEventListener("keydown", e => { if (e.key !== "Escape") return; e.stopPropagation(); e.preventDefault();
      if (P.q.value) { P.q.value = ""; filter(); return; } P.q.blur(); const b = document.getElementById("bkeys"); if (b) b.click(); });
  }
  function count() {
    const n = P.all.querySelectorAll(".kp-row").length;
    P.panel.querySelector('[data-kt="all"].kp-tab em').textContent = n;
    P.panel.querySelector(".kp-lnk").textContent = t("All {n}", { n });
  }
  function show(which) {
    const tabs = P.panel.querySelector(".kp-tabs"); tabs.setAttribute("value", which);   // the primitive marks the chosen tab (before it is defined: these marks)
    P.panel.querySelectorAll(".kp-tab").forEach(b => { const on = b.dataset.kt === which; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
    P.panel.querySelectorAll(".kp-body > section").forEach(s => { s.hidden = s.dataset.kt !== which; });
    filter();
  }
  function filter() {
    const q = P.q.value.trim().toLowerCase(), sec = P.panel.querySelector(".kp-body > section:not([hidden])");
    let shown = 0;
    sec.querySelectorAll(".kp-row, .kp-tip").forEach(r => { const hit = !q || r.textContent.toLowerCase().includes(q); r.hidden = !hit; shown += hit; });
    sec.querySelectorAll(".kp-lb").forEach(l => { const list = l.nextElementSibling; l.hidden = !!q && !list.querySelector(":scope > :not([hidden])"); });
    P.none.hidden = shown > 0; P.none.textContent = t("Nothing found");
  }
  // a row another module adds to #keys: into All keys (Arrange's after ⌥D, as before)
  function adopt(row) {
    if (!(row instanceof HTMLElement) || row.parentElement !== P.panel || row.classList.contains("kp-in")) return;
    if (row.hasAttribute("data-arrange-keys")) {
      const after = [...P.all.querySelectorAll("[data-arrange-keys]")].pop() || [...P.all.children].find(d => /⌥\s*D/.test(d.querySelector(".k")?.textContent || ""));
      if (after) after.after(row); else P.all.append(row);
    } else P.all.append(row);
    dress(row);
  }
  function start() {
    const panel = document.getElementById("keys"); if (!panel || P) return;
    build(panel);
    new MutationObserver(ms => { let n = 0; ms.forEach(m => m.addedNodes.forEach(r => { if (r.parentElement === panel && !r.classList?.contains("kp-in")) { adopt(r); n++; } }));
      if (n) { count(); filter(); } }).observe(panel, { childList: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  window.hyKeysPanel = { ICON, dress, show, get parts() { return P; } };
})();
