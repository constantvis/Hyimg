// The settings, one component for Home and every board (owner 2026-10-07: «настройки причесать, переключатели странные ... и
// настройки на доске отличаются от настроек тут»). Both pages had their own copy of the markup and drifted apart (the board had no «Hide
// interface», its Reset looked different). Now the rows, their order, their words and their look live here; a page says only how it reads
// and writes a setting. Since 2026-10-08 they stand in a window of their own inside the page (ui/settings-win.js, E1 «Rail popover» of
// Concepts/html/settings-concepts: «изначально ты нажимаешь, у тебя прям настройки открываются широко, красиво, а не в углу»): a rail of
// sections on the left, one section on the right. Profile and Team (ui/people.js), Notifications (ui/macnotif.js), Plugins (ui/plugins.js)
// and Storage (ui/storage.js) add their sections to the same window.
//
// The rows here, by section: Appearance (language, theme, corners, shadows, notes; the visual choices with live previews), Board (the
// paper's colour and grain, the dots' visibility, the boards' sleep, board links in the app), Interface (how ⌘. hides it, key hints),
// Performance (engine, rendering, how the dots are drawn) with Diagnostics (the performance log). One row a setting: the name on the left
// with the chosen option's words under it, the control on the right, or under the name when the row is too narrow for both.
// The reset of the paper is a plain <hy-button>, the dots' visibility the app's slider. Home loads the primitives' CSS but not their module (it is a file page), so the controls here
// work without the elements being upgraded too: this file keeps the chosen option's class and ARIA itself, answers the arrow keys and
// writes a switch's checkbox; where the module runs (a board) the element does the same and this file listens to its hy-change.
// Since round 11 (owner 2026-10-08: «В обеих вроде все нравится») every control lies in a dark well: a choice is <hy-segmented
// variant=well> (the chosen option on a grey plate), an on/off <hy-switch variant=well>, a visual choice its pictures in a well with the
// chosen one on the same grey plate (the thumb slides). The settings stand at the side of a board or in a window (ui/settings-win.js);
// a row lays itself out for the width it has (fit).
//
//   const P = hySetPanel.mount(document.getElementById("sets"), {
//     get(key)        -> the setting's value now, a string (lang, theme, shape, shadow, glass, paperDark, paperLight, grain, dotsv,
//                        engine, lod, dotsgl, sleep, hideui, applinks, keyhint, perflog); empty: the row's def
//     set(changes)    the person changed {key: value}; null takes a setting back to its default (the paper's Reset)
//     engine()        -> true when the Engine row is shown (inside the Mac app)
//   })
//   P.refresh()       the controls show what get() says now (after a page changed a setting itself, or the settings came from elsewhere)
//   P.go(section)     shows a section: profile, team, appearance, board, notifications, plugins, storage, interface, performance
//   hySetPanel.body() the element the sections stand in (the modules put theirs there)
(() => {
  if (window.hySetPanel) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  for (const f of ["setpanel.css", "settings-win.css"]) {
    if (document.querySelector(`link[href$="ui/${f}"]`)) continue;
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL(f, SRC).href; (document.head || document.documentElement).appendChild(l);
  }
  const T = k => (window.T ? window.T(k) : String(k).replace(/^\w+::/, ""));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  // [value, words, tooltip]; the languages are named in themselves, never translated; «theme::», «grain::»: words the library says otherwise.
  // pv: a choice shown as small pictures of the app (its look under each option); sw: on and off, [off tooltip, on tooltip]
  const ROWS = [
    ["appearance", "", [
      { k: "lang", label: "Language", own: true, opts: [["en", "English"], ["ru", "Русский"]] },   // hy-allow: cyrillic-code the language named in itself
      { k: "theme", label: "Theme", pv: true, opts: [["auto", "Auto", "Like macOS: light by day, dark in the evening, if the system is set that way"],
        ["dark", "Dark", "Dark theme, graphite paper"], ["light", "theme::Light", "Light theme, light paper"]] },
      { k: "shape", label: "Corners", pv: true, opts: [["round", "Round", "Round buttons and panels"], ["pro", "Pro", "Stricter: almost square, with a moderate radius"]] },
      // owner 2026-10-08: a middle choice, the panels with a shadow and the top row and the dock flat; none by default (ui/tokens.css)
      { k: "shadow", label: "Shadows", def: "0", pv: true, opts: [["1", "With shadows", "Panels and buttons float above the board"],
        ["panels", "Panels only", "Panels and menus float, the top row and the dock lie flat"], ["0", "No shadows", "Everything lies flat"]] },
      { k: "glass", label: "Notes", pv: true, opts: [["1", "Glass", "Translucent, with a strong blur under them"], ["0", "Solid", "Solid, no blur"]] },
    ]],
    ["board", "", [
      { k: "paper", label: "Paper color", paper: true },
      { k: "grain", label: "Paper grain", pv: true, opts: [["0", "Very fine"], ["1", "grain::Fine"], ["2", "Visible"], ["3", "grain::Strong"]] },
      { k: "dotsv", slider: true },
    ]],
    ["board", "", [
      // a board left behind gives its page's memory back, its server goes on (owner 2026-10-08, native/BoardSleep.swift)
      { k: "sleep", label: "Sleep background boards", def: "10", opts: [["5", "5 min", "A board left for 5 minutes gives its memory back, its server keeps working"],
        ["10", "10 min", "A board left for 10 minutes gives its memory back, its server keeps working"],
        ["30", "30 min", "A board left for 30 minutes gives its memory back, its server keeps working"], ["0", "Never", "Boards left behind keep their pages and memory"]] },
      // a board's http link opened in a browser (owner 2026-10-07): it offers Hyimg on a plate, or goes there by itself (ui/applink.js)
      { k: "applinks", label: "Open board links in the app", def: "0", sw: ["A board link opened in a browser stays there and offers Hyimg",
        "A board link opened in a browser goes straight to Hyimg"] },
    ]],
    ["interface", "", [
      { k: "hideui", label: "Hide interface · ⌘.", opts: [["zoom", "Zoom", "Everything around the board grows a little and fades out"],
        ["slide", "Slide", "Everything slides off to its edge and fades"]] },
      // the Hints family (DESIGN.md «Семья подсказок»): key hints, the Hint bar and the tips, until learned by default (ui/hy/keyhint.js, tip.js)
      { k: "keyhint", label: "Key hints", def: "learn", opts: [["always", "Always", "Key hints and tips always show, learned ones too"],
        ["learn", "Until learned", "A key used 5 times and a tip used once are no longer shown"], ["off", "Off", "No key hints, Hint bar or tips"]] },
    ]],
    ["performance", "", [
      { k: "engine", label: "Engine", opts: [["webkit", "WebKit", "The macOS engine, like Safari: draws on the CPU"],
        ["chromium", "Chromium", "Chrome's engine inside Hyimg: the GPU draws the board and it stays smooth"]] },
      { k: "lod", label: "Rendering", opts: [["0", "Standard", "Each image as its own element"], ["1", "Canvas", "From afar the images are drawn as one canvas (canvas 2D)"],
        ["2", "WebGL", "From afar the GPU draws the images (WebGL), like Figma"]] },
      { k: "dotsgl", label: "Dots", opts: [["0", "Classic", "A grid of CSS layers, as always"], ["1", "WebGL", "One WebGL layer: alive, waves run through them when you drop images"]] },
    ]],
    // frame drops written down with what was on screen, for finding a lag later (owner 2026-10-08, ui/perflog.js, review/perflog.py);
    // on until turned off (owner 2026-10-08: «сделай так, чтобы он по умолчанию был включен»)
    ["performance", "Diagnostics", [
      { k: "perflog", label: "Performance log", def: "1", sw: ["Nothing is written",
        "When frames drop, a line with what was on screen goes into the app's cache; its size is under Storage"] },
    ]],
  ];
  const ALL = ROWS.flatMap(([, , rows]) => rows), BY = Object.fromEntries(ALL.map(r => [r.k, r]));
  const DEF = Object.fromEntries(ALL.filter(r => r.def).map(r => [r.k, r.def]));   // a setting's value until it is set
  const val = (api, k) => { const v = api.get(k); return v == null || v === "" ? DEF[k] || "" : v; };
  // the words under a row's name: what the chosen option does (its tooltip), or the switch's state
  const tipOf = (r, v) => r.sw ? r.sw[v === "1" ? 1 : 0] : ((r.opts || []).find(o => o[0] === v) || [])[2] || "";
  // a primitive is upgraded on a board (ui/hy/index.js), maybe not yet when this draws; Home only links its CSS: the control is written here
  const UP = n => !!(window.customElements && customElements.get(n)) || !!document.querySelector('script[type="module"][src$="hy/index.js"]');

  // the small pictures of a visual choice: the app's top row, two pictures, a panel and the dock, in that option's look ------------------
  const scene = (cls = "", attrs = "") => `<span class="sp-mini${cls}"${attrs} aria-hidden="true"><i class="m-top"></i><i class="m-top2"></i>`
    + `<i class="m-pic"></i><i class="m-pic2"></i><i class="m-pan"></i><i class="m-dock"></i></span>`;
  function pvHtml(k, v, api) {
    if (k === "theme") return v === "auto" ? scene("", ' data-hy-theme="dark"') + scene(" sp-half", ' data-hy-theme="light"')
      : scene("", ` data-hy-theme="${v === "light" ? "light" : "dark"}"`);
    if (k === "shape") return scene("", ` data-hy-shape="${v}"`);
    if (k === "shadow") return scene(v === "1" ? " sh1" : v === "panels" ? " shp" : "");
    if (k === "glass") return `<span class="sp-mini sp-photo" aria-hidden="true"><i class="m-note${v === "1" ? " glass" : ""}"></i></span>`;
    if (k === "grain") {   // the paper itself (ui/paper.js), in the theme in use
      const light = document.documentElement.dataset.theme === "light", P = window.hyPaper;
      const bg = P ? P.css(light ? "light" : "graphite", +v, api.get(light ? "paperLight" : "paperDark")) : "";
      return `<span class="sp-mini sp-grain" aria-hidden="true" style="background:${esc(bg)}"></span>`;
    }
    return "";
  }
  const optHtml = (r, [v, words, tip], api) => `<button type="button" value="${v}" data-v="${v}"${r.own ? ` lang="${v}"` : ""}`
    + `${tip ? ` title="${esc(T(tip))}"` : ""}>` + (r.pv ? `<span class="sp-pvi">${pvHtml(r.k, v, api)}</span><span class="sp-pvl">${esc(T(words))}</span>`
      : esc(r.own ? words : T(words))) + "</button>";
  // the words a search finds a row by besides what it shows: every option's words and tooltip
  const words = r => esc([...(r.opts || []).flatMap(o => [r.own ? o[1] : T(o[1]), o[2] ? T(o[2]) : ""]), ...(r.sw || []).map(T)].join(" "));
  function rowHtml(r, api) {
    if (r.slider) return `<div class="sp-row sp-wide" data-row="${r.k}"><div class="hy-slider" data-unit="%"><input id="dotsVis" type="range" min="0" max="300" step="5" `
      + `aria-label="${esc(T("Dots visibility, percent"))}"><span class="hy-slider-l">${esc(T("Dots visibility"))}</span><output class="hy-slider-v"></output></div></div>`;
    const name = `<span class="sp-lw"><span class="sp-l" id="sp-l-${r.k}">${esc(T(r.label))}</span>`
      + ((r.opts || []).some(o => o[2]) || r.sw ? `<span class="hy-hint sp-h" data-tip="${r.k}"></span>` : "") + "</span>";
    if (r.paper) return `<div class="sp-row" data-row="paper">${name}<span class="sp-c sp-paper">`
      + `<input type="color" data-paper="paperDark" title="${esc(T("Paper color in the dark theme"))}" aria-label="${esc(T("Paper color in the dark theme"))}">`
      + `<input type="color" data-paper="paperLight" title="${esc(T("Paper color in the light theme"))}" aria-label="${esc(T("Paper color in the light theme"))}">`
      + `<hy-button size="s" data-paper-reset title="${esc(T("Restore the default colors"))}">${esc(T("Reset"))}</hy-button></span></div>`;
    if (r.sw) return `<label class="sp-row sp-swr" data-row="${r.k}" data-words="${words(r)}">${name}<hy-switch class="sp-c" variant="well" data-set-sw="${r.k}" label="${esc(T(r.label))}">`
      + (UP("hy-switch") ? "" : `<input type="checkbox" class="hy-in" role="switch" aria-label="${esc(T(r.label))}">`) + "</hy-switch></label>";
    const cls = (r.pv ? " sp-pvrow" : "") + (r.pv && r.opts.length > 2 ? " sp-many" : "");
    return `<div class="sp-row${cls}" data-row="${r.k}" data-words="${words(r)}"${r.k === "engine" ? ' id="engineSet" hidden' : ""}>${name}`
      + `<hy-segmented class="seg sp-c${r.pv ? " sp-pvs" : ""}" variant="well" data-set="${r.k}" label="${esc(T(r.label))}"${r.own ? " data-not" : ""}>`
      + r.opts.map(o => optHtml(r, o, api)).join("") + "</hy-segmented></div>";
  }
  const html = api => ROWS.map(([sec, head, rows], i) => `<section class="sp-g" data-sec="${sec}"${head ? ` aria-labelledby="sp-h-${i}"` : ""}>`
    + (head ? `<div class="sh" id="sp-h-${i}">${esc(T(head))}</div>` : "") + `<div class="sp-card">${rows.map(r => rowHtml(r, api)).join("")}</div></section>`).join("");

  // a choice's chosen option, its class and ARIA (what <hy-segmented> does when its module runs; Home has the element un-upgraded)
  function show(seg, v) {
    if (seg.getAttribute("value") !== v) seg.setAttribute("value", v);
    seg.setAttribute("role", "radiogroup");
    for (const b of seg.querySelectorAll(":scope > button")) {
      const on = b.value === v;
      b.classList.toggle("on", on); b.setAttribute("role", "radio"); b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1;
    }
  }

  // sections of their own with the same api: Notifications (ui/macnotif.js, owner 2026-10-08), loaded from here so neither page needs a tag
  function sections(el, api) {
    const go = () => window.hyMacNotif && window.hyMacNotif.mount(el, api);
    if (window.hyMacNotif) { go(); return; }
    const s = document.createElement("script"); s.src = new URL("macnotif.js", SRC).href; s.onload = go; document.head.appendChild(s);
  }

  let WIN = null;
  function mount(el, api) {
    // the window: a rail of sections, the section on the right (ui/settings-win.js); without it the rows stand in the page's element
    const hooks = {};   // fit, once the rows are there
    WIN = window.hySetWin ? window.hySetWin.build(el, hooks) : null;
    const body = WIN ? WIN.body : el;
    const box = document.createElement("div"); box.className = "sp"; box.innerHTML = html(api);
    body.prepend(box);
    sections(body, api);
    if (window.hySeg) window.hySeg(box);
    const slider = window.hySlider ? window.hySlider.mount(box.querySelector(".hy-slider")) : null;
    const wait = {};   // a choice the page takes in its own time (the language reloads the page, the engine restarts the board): shown at once
    // the Reset of the paper: a real button inside once <hy-button> is upgraded; on Home (not upgraded) the element itself is the button
    const reset = box.querySelector("[data-paper-reset]");
    if (!(window.customElements && customElements.get("hy-button"))) {
      reset.setAttribute("role", "button"); reset.tabIndex = 0;
      if (window.customElements) customElements.whenDefined("hy-button").then(() => { reset.removeAttribute("role"); reset.removeAttribute("tabindex"); });
    }
    const now = k => String(wait[k] ?? val(api, k));

    function refresh() {
      const eng = !!(api.engine && api.engine());
      box.querySelector("#engineSet").hidden = !eng;
      box.querySelectorAll("hy-segmented[data-set]").forEach(s => show(s, now(s.dataset.set)));
      box.querySelectorAll("hy-switch[data-set-sw]").forEach(s => {
        const on = now(s.dataset.setSw) === "1", i = s.querySelector("input");
        s.toggleAttribute("checked", on); if (i) i.checked = on;
      });
      box.querySelectorAll("[data-tip]").forEach(h => { const t = tipOf(BY[h.dataset.tip], now(h.dataset.tip)); if (h.textContent !== T(t)) h.textContent = t ? T(t) : ""; });
      box.querySelectorAll("[data-paper]").forEach(i => { const v = api.get(i.dataset.paper); if (v && i.value !== v) i.value = v; });
      // the grain's pictures are the paper in the theme in use, in its colour: drawn again when either changed
      const g = box.querySelector("hy-segmented[data-set=grain]"), gk = document.documentElement.dataset.theme + api.get("paperDark") + api.get("paperLight");
      if (g && g._k !== gk) { g._k = gk; g.querySelectorAll(":scope > button").forEach(b => { b.querySelector(".sp-pvi").innerHTML = pvHtml("grain", b.value, api); }); }
      if (slider) slider.set(api.get("dotsv"));
      if (window.hyMacNotif) window.hyMacNotif.paint();
      fit(); if (WIN) WIN.sums();
    }
    // the name and the control side by side, or the control under the name when they do not fit (measured while the row is shown); at
    // the side a visual choice of three or more always goes under its name, across the row (round 11's settings-side.html)
    function fit() {
      if (!body.offsetWidth) return;
      const side = !!WIN && WIN.side();
      box.querySelectorAll(".sp-row:not(.sp-wide)").forEach(r => {
        if (r.hidden || !r.offsetWidth) return;
        const s = r.querySelector("hy-segmented"), pv = r.classList.contains("sp-pvrow"), l = r.querySelector(".sp-l"), c = r.querySelector(".sp-c");
        r.classList.remove("sp-stack"); if (s && !pv) s.removeAttribute("full");
        const cs = getComputedStyle(r), room = r.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);   // the name is as wide as its words
        if (!(side && r.classList.contains("sp-many")) && (!l || !c || l.scrollWidth + parseFloat(cs.columnGap) + c.offsetWidth <= room + 1)) return;
        r.classList.add("sp-stack"); if (s && !pv) s.setAttribute("full", "");
      });
    }
    new ResizeObserver(() => fit()).observe(body);

    function choose(seg, v) {
      const k = seg.dataset.set;
      if (v == null || v === now(k)) { show(seg, now(k)); return; }
      if (k === "lang" || k === "engine") wait[k] = v;
      show(seg, v); api.set({ [k]: v }); refresh();
    }
    const upgraded = seg => !!(window.customElements && customElements.get("hy-segmented") && seg.matches(":defined"));
    box.addEventListener("hy-change", e => {
      const s = e.target.closest("hy-segmented[data-set]"); if (s) { choose(s, e.detail && e.detail.value); return; }
      const w = e.target.closest("hy-switch[data-set-sw]"); if (w) flip(w, !!(e.detail && e.detail.checked));
    });
    // a switch: "1" on, "0" off, written either way (a default may change, the person's choice stays)
    function flip(w, on) { w.toggleAttribute("checked", on); api.set({ [w.dataset.setSw]: on ? "1" : "0" }); refresh(); }
    box.addEventListener("change", e => {
      const w = e.target.closest("hy-switch[data-set-sw]"); if (!w || e.target.localName !== "input" || UP("hy-switch") && w.matches(":defined")) return;
      flip(w, e.target.checked);
    });
    box.addEventListener("click", e => {
      if (e.target.closest("[data-paper-reset]")) { api.set({ paperDark: null, paperLight: null }); refresh(); return; }
      const b = e.target.closest("hy-segmented[data-set] > button"); if (!b || b.disabled) return;
      if (!upgraded(b.parentElement)) choose(b.parentElement, b.value);   // an upgraded element sends hy-change itself
    });
    box.addEventListener("keydown", e => {
      if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-paper-reset][role=button]")) { e.preventDefault(); e.target.click(); return; }
      const b = e.target.closest("hy-segmented[data-set] > button"); if (!b || upgraded(b.parentElement)) return;
      const all = [...b.parentElement.querySelectorAll(":scope > button:not(:disabled)")], i = all.indexOf(b), n = all.length;
      const j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: n - 1 }[e.key];
      if (j === undefined) return;
      e.preventDefault(); const to = all[(j + n) % n]; to.focus(); choose(b.parentElement, to.value);
    });
    // the paper's colours follow the picker as it moves; the dots' visibility follows the slider
    box.addEventListener("input", e => {
      const p = e.target.closest("[data-paper]"); if (p) { api.set({ [p.dataset.paper]: p.value }); refresh(); return; }
      if (e.target.id === "dotsVis") api.set({ dotsv: e.target.value });
    });
    hooks.fit = fit;
    refresh();
    return { el: box, refresh, fit, go: id => WIN && WIN.go(id) };
  }
  window.hySetPanel = { mount, ROWS, body: () => (WIN ? WIN.body : document.getElementById("sets")), go: id => WIN && WIN.go(id) };
})();
