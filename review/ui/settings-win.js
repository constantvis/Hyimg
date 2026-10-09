// The settings of the whole app, Home's and every board's, in two ways (owner 2026-10-08, round 11 of Concepts/html/editors-concepts:
// r11/settings-side.html and r11/settings-full.html, «В обеих вроде все нравится, кроме вот этого комментария»).
//
// At the side (a board's default): a panel docked at the right edge, full height under the top row, the board live and working beside it,
// so every change shows on it at once. Its header «Settings» with «Open as a window» and close, the search, then every section one under
// the other, each under its header (a chevron folds it, the words at its right end say what is chosen in it). The strip of the sections'
// icons the concept had under the search is not there (the owner's comment c43bcc5daff on it: «Так вот этот элемент можно убрать. Он тут
// лишний»). Its left edge sets its width, the viewer's.
//
// As a window (E1 «Rail popover», 2026-10-08: «как будто бы мы открываем другое окно, но на самом деле мы просто поверх текущего сейчас
// внутри окна открываем настройки»): a veil over the page, the window in the middle, wide (min(1100 px, 90 %) by min(760 px, 85 %)),
// resized by its edges and corners up to the whole window, symmetrically, so it stays in the middle; a double click on its title fills the
// window or gives the size back. Left, a rail: search, the profile, the sections; right, the section chosen, «Dock to the side» and close.
//
// Which of the two: «Dock to the side» and «Open as a window» in its header, kept in the app's settings (cv.setsdock: "window" or nothing),
// the same on every board of this Mac. Home has nothing beside the panel to keep live (no paper, dots or notes) and its cards only scroll
// down, so a panel at its side would only hide a column of them: Home keeps the window (its #sets carries data-sw-window).
//
// Both: the search finds rows in every section by their names, options and hints, marks the words found (the CSS highlight API) and
// counts them; Esc closes it (the first one clears the search; at the side only while the panel has the keyboard, else Esc is the
// board's); the settings button and close close it, and the veil the window. It opens and closes with the app's curve, at once with
// «Reduce motion». The controls lie in dark wells, the chosen thing on a grey plate (ui/hy variant=well; round 11 keeps the grey, the
// blue ring of the selection is still the owner's open question).
//
// The page's #sets stays the dialog: the page toggles its class «open» as before, this file follows. The sections stand in .sw-body:
// ui/setpanel.js puts its rows there, ui/people.js, macnotif.js, plugins.js and storage.js theirs (hySetPanel.body()). A section is any
// element with data-sec (the modules' own get it here by their id).
//   const W = hySetWin.build(el, { fit })   fit: called when rows come into view or the panel changed its width (the rows measure themselves)
//   W.body, W.go(section), W.search(words), W.sync(), W.sums(), W.side()
(() => {
  if (window.hySetWin) return;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/^\w+::/, "").replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m)));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const ic = (n, s = 16, w = 1.85) => (window.hyIcon ? window.hyIcon(n, s, w) : "");
  const store = { get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };
  // the sections in the rail's order (a null is its hairline); Profile is the face at the top of the rail
  const SECS = [["profile", "Profile", "person"], ["team", "Team & agents", "team"], null, ["appearance", "Appearance", "palette"], ["board", "set::Board", "board"],
    ["notifications", "set::Notifications", "notifications"], ["plugins", "Plugins", "plugin"], ["storage", "Storage", "drive"], null,
    ["interface", "Interface", "keyboard"], ["performance", "Performance", "gauge"]];
  const LIST = SECS.filter(Boolean), NAME = Object.fromEntries(LIST.map(([id, n, i]) => [id, [n, i]]));
  const MODULE = { hyMacNotif: "notifications", hyPlugSet: "plugins", hyStore: "storage" };   // the modules' sections, by their id
  const ROW = ".sp-row, .mn-row, .hpl-row, .hs-row";
  const MIN_W = 640, MIN_H = 420, SIZE = "hy.sets.size", SEC = "hy.sets.sec", SIDE_W = "hy.sets.side", SHUT = "hy.sets.shut";
  const DOCK = "cv.setsdock";   // the app's setting (server.py APP_KEYS): "window", or nothing for the side
  const SW_MIN = 320, SW_DEF = 412;
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cap = s => s ? s[0].toUpperCase() + s.slice(1) : "";

  function build(el, o = {}) {
    const kids = [...el.childNodes], dockable = !el.hasAttribute("data-sw-window");
    el.classList.add("hy-setwin"); el.setAttribute("aria-modal", "true"); el.dataset.swGone = "";
    if (el.parentElement !== document.body) document.body.appendChild(el);   // a board's #sets stood in #stage: over the whole page now
    const nav = SECS.slice(2).map(s => s ? `<button type="button" class="sw-nv" data-go="${s[0]}">${ic(s[2])}<span class="sw-nt">${esc(T(s[1]))}</span>`
      + `<span class="sw-n"></span></button>` : '<div class="sw-sep" role="presentation"></div>').join("");
    // a header's key: the app's icon button (Home does not upgrade it: role and keys are given below)
    const hb = (act, icon, words) => `<hy-icon-button class="sw-hb" size="m" data-sw-act="${act}" label="${esc(T(words))}" title="${esc(T(words))}">${ic(icon, 15)}</hy-icon-button>`;
    el.innerHTML = `<div class="sw-veil"></div><div class="sw-box"><div class="sw-rail" role="navigation" aria-label="${esc(T("Settings sections"))}">`
      + `<label class="hy-search sw-q">${ic("search", 15, 2)}<input type="search" placeholder="${esc(T("set::Search"))}" aria-label="${esc(T("Search settings"))}" `
      + `spellcheck="false" autocomplete="off"><span class="sw-qn" aria-live="polite"></span></label>`
      + `<button type="button" class="sw-nv sw-me" data-go="profile"><span class="sw-av"></span><span class="sw-mt"><b></b><span>${esc(T("Profile, folders"))}</span></span>`
      + `<span class="sw-n"></span></button><button type="button" class="sw-nv" data-go="team">${ic("team")}<span class="sw-nt">${esc(T("Team & agents"))}</span>`
      + `<span class="sw-n"></span></button><div class="sw-sep" role="presentation"></div>${nav}`
      + `<div class="hy-hint sw-foot">${T("For <b>the whole app</b>: Home and every board")}</div></div>`
      + `<div class="sw-pane"><header class="sw-hd"><h2 id="sw-h"></h2><span class="hy-hint sw-cnt"></span>`
      + (dockable ? hb("mode", "dockSide", "Dock to the side") : "") + hb("close", "close", "Close · Esc") + "</header>"
      + `<div class="sw-body" role="region" aria-labelledby="sw-h"></div></div>`
      + ["n", "s", "e", "w", "ne", "nw", "se", "sw"].map(d => `<i class="sw-rz" data-rz="${d}" aria-hidden="true"></i>`).join("") + "</div>";
    const $ = s => el.querySelector(s), box = $(".sw-box"), rail = $(".sw-rail"), pane = $(".sw-pane"), body = $(".sw-body"), q = $(".sw-q input");
    const qLabel = $(".sw-q"), foot = $(".sw-foot"), head = $("#sw-h"), cnt = $(".sw-cnt"), qn = $(".sw-qn"), hd = $(".sw-hd");
    body.append(...kids);
    // the sections' headers: at the side always, each folds its section; in the window they stand above each section's rows found
    body.insertAdjacentHTML("beforeend", LIST.map(([id, n, i]) => `<button type="button" class="sw-sl" data-for="${id}" aria-expanded="true">`
      + `<span class="sw-cv" aria-hidden="true">${ic("chevron", 11, 2.4)}</span>${ic(i, 14)}<span class="sw-st">${esc(T(n))}</span>`
      + `<span class="sw-sum"></span></button>`).join(""));
    // Home does not upgrade the app's elements: its header keys are buttons for the keyboard here
    if (!(window.customElements && customElements.get("hy-icon-button"))) el.querySelectorAll(".sw-hb").forEach(b => {
      b.setAttribute("role", "button"); b.setAttribute("aria-label", b.getAttribute("label")); b.tabIndex = 0;
      if (window.customElements) customElements.whenDefined("hy-icon-button").then(() => { b.removeAttribute("role"); b.removeAttribute("tabindex"); });
    });
    let cur = NAME[store.get(SEC)] ? store.get(SEC) : "appearance", Q = "";
    const shut = new Set(Array.isArray(store.get(SHUT)) ? store.get(SHUT) : ["profile", "team"]);   // the side's folded sections, the viewer's

    // which of the two: the side unless the person chose the window (the app's setting, the same on every board) --------------------------
    const side = () => el.classList.contains("sw-side");
    const want = () => { if (!dockable) return false; try { return localStorage.getItem(DOCK) !== "window"; } catch { return true; } };
    function mode(s) {
      el.classList.toggle("sw-side", s);
      if (s) { pane.insertBefore(qLabel, body); pane.appendChild(foot); } else { rail.prepend(qLabel); rail.appendChild(foot); }
      const m = el.querySelector("[data-sw-act=mode]");
      if (m) {
        const [icon, words] = s ? ["asWindow", "Open as a window"] : ["dockSide", "Dock to the side"];
        m.setAttribute("label", T(words)); m.title = T(words); if (m.hasAttribute("aria-label")) m.setAttribute("aria-label", T(words));
        const g = m.querySelector("svg:not(.hy-i)"); if (g) g.outerHTML = ic(icon, 15);
        const inner = m.querySelector("button"); if (inner) { inner.title = T(words); inner.setAttribute("aria-label", T(words)); }
      }
      hd.title = s ? "" : T("Double-click: the whole window or back");
      el.setAttribute("aria-modal", String(!s));
      document.documentElement.classList.toggle("hy-sets-dock", s && el.classList.contains("open"));
      full();
    }
    function toggleMode() {
      const s = !side();
      try { if (s) localStorage.removeItem(DOCK); else localStorage.setItem(DOCK, "window"); } catch {}
      delete el.dataset.swShown; mode(s); paint(); void el.offsetWidth; el.dataset.swShown = "";
      if (s) { const c = body.querySelector(`.sw-sl[data-for="${cur}"]`); if (c && !Q) { shut.delete(cur); keepShut(); paint(); scrollTo(c); } }
      if (o.fit) o.fit();
    }

    // the window's size: the viewer's, in px; a number past the window is the whole window (CSS max-width, max-height)
    const size = store.get(SIZE) || {};
    let tw = 0, th = 0;   // the size asked for (0: the default); the box may still be easing towards it
    function setSize(w, h) {
      tw = w || 0; th = h || 0;
      if (w) box.style.setProperty("--sw-w", Math.round(w) + "px"); else box.style.removeProperty("--sw-w");
      if (h) box.style.setProperty("--sw-h", Math.round(h) + "px"); else box.style.removeProperty("--sw-h");
      full();
    }
    const full = () => box.classList.toggle("sw-full", !side() && !!el.clientWidth && tw >= el.clientWidth - 1 && th >= el.clientHeight - 1);
    setSize(size.full ? 1e5 : size.w, size.full ? 1e5 : size.h);
    // the side's width: the viewer's, never more than most of the window
    const sideMax = () => Math.max(SW_MIN, Math.min(760, Math.round((el.clientWidth || innerWidth) * 0.7)));
    const setSide = w => box.style.setProperty("--sw-sw", Math.round(Math.max(SW_MIN, Math.min(sideMax(), w || SW_DEF))) + "px");
    setSide(store.get(SIDE_W));
    addEventListener("resize", () => { if (!("swGone" in el.dataset)) full(); });

    // which sections stand in the body now: the modules' get their data-sec, the order of the rail ---------------------------------------
    function tag() {
      for (const [id, s] of Object.entries(MODULE)) { const m = document.getElementById(id); if (m && m.dataset.sec !== s) m.dataset.sec = s; }
      body.querySelectorAll("[data-sec]").forEach(g => { const n = LIST.findIndex(s => s[0] === g.dataset.sec); g.style.order = String(n * 2 + 1); });
      body.querySelectorAll(".sw-sl").forEach(l => { l.style.order = String(LIST.findIndex(s => s[0] === l.dataset.for) * 2); });
    }
    function paint() {
      tag();
      const hits = {}, S = side();
      const groups = [...body.querySelectorAll("[data-sec]")], has = new Set(groups.map(g => g.dataset.sec));
      if (!Q) groups.forEach(g => g.classList.toggle("sw-on", S ? !shut.has(g.dataset.sec) : g.dataset.sec === cur));
      else for (const g of groups) {
        const sec = g.dataset.sec, all = T(NAME[sec][0]).toLowerCase().includes(Q), rows = [...g.querySelectorAll(ROW)];
        let n = 0;
        for (const r of rows) { const ok = all || words(r).includes(Q); r.classList.toggle("sw-miss", !ok); if (ok && !r.closest(".sw-miss")) n++; }
        const on = rows.length ? n > 0 : all;
        g.classList.toggle("sw-on", on); if (on) hits[sec] = (hits[sec] || 0) + Math.max(n, 1);
      }
      if (!Q) body.querySelectorAll(".sw-miss").forEach(r => r.classList.remove("sw-miss"));
      let first = true;
      [...body.querySelectorAll(".sw-sl")].sort((a, b) => a.style.order - b.style.order).forEach(l => {
        const id = l.dataset.for, on = Q ? !!hits[id] : S && has.has(id), open = !!Q || !shut.has(id);
        l.classList.toggle("sw-on", on); l.classList.toggle("sw-shut", S && !open); l.setAttribute("aria-expanded", String(!S || open));
        l.title = S && !Q ? T("Fold or unfold") : ""; l.classList.toggle("sw-first", on && first); if (on) first = false;
      });
      el.querySelectorAll(".sw-rail [data-go]").forEach(b => {
        const id = b.dataset.go, n = hits[id] || 0, on = !Q && id === cur;
        b.classList.toggle("on", on); b.toggleAttribute("aria-current", on); if (on) b.setAttribute("aria-current", "page");
        b.classList.toggle("dim", !!Q && !n); b.querySelector(".sw-n").textContent = Q && n ? String(n) : "";
      });
      const total = Object.values(hits).reduce((a, b) => a + b, 0);
      head.innerHTML = S ? `${ic("settings", 15)}<span>${esc(T("set::Settings"))}</span>`
        : Q ? `${ic("search")}<span>${esc(T("set::Search"))}</span>` : `${ic(NAME[cur][1])}<span>${esc(T(NAME[cur][0]))}</span>`;
      cnt.textContent = Q ? (total ? T("{n} found", { n: total }) : T("Nothing found")) : "";
      qn.textContent = Q ? (total ? String(total) : "0") : "";
      el.classList.toggle("sw-qon", !!Q);
      mark(); sums();
      if (o.fit) o.fit();
      heads();
    }
    // at the side only the header of the section at the top sticks there (the ones scrolled past would lie stuck under it): where each
    // header stands is read with none of them stuck, then the one whose place the scroll has passed last sticks
    let tops = [];
    function heads() {
      const ls = [...body.querySelectorAll(".sw-sl")];
      ls.forEach(l => l.classList.remove("sw-stuck"));
      tops = side() ? ls.filter(l => l.offsetParent).map(l => [l, l.offsetTop]).sort((a, b) => a[1] - b[1]) : [];
      stick();
    }
    function stick() {
      let c = null; for (const [l, t] of tops) if (t <= body.scrollTop + 0.5) c = l;
      for (const [l] of tops) l.classList.toggle("sw-stuck", l === c);
    }
    body.addEventListener("scroll", stick, { passive: true });
    new ResizeObserver(() => requestAnimationFrame(() => { if (side() && !("swGone" in el.dataset)) heads(); })).observe(body);   // after the rows restacked
    // what a row is found by: its words, its tooltips and labels, the options' words (data-words, ui/setpanel.js)
    const words = r => (r.textContent + " " + [r, ...r.querySelectorAll("[title], [aria-label]")].map(e => `${e.getAttribute("title") || ""} ${e.getAttribute("aria-label") || ""}`).join(" ")
      + " " + (r.dataset.words || "")).toLowerCase();
    // the words found, marked without touching the rows (the modules draw them again whenever they like)
    function mark() {
      const H = window.CSS && CSS.highlights; if (!H || typeof Highlight !== "function") return;
      if (!Q) { H.delete("hy-set-q"); return; }
      const ranges = [], tw = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      for (let t = tw.nextNode(); t; t = tw.nextNode()) {
        const p = t.parentElement; if (!p || !p.closest(ROW) || p.closest(".sw-miss, [data-sec]:not(.sw-on), svg")) continue;
        const s = t.data.toLowerCase(); let i = s.indexOf(Q);
        while (i >= 0) { const r = new Range(); r.setStart(t, i); r.setEnd(t, i + Q.length); ranges.push(r); i = s.indexOf(Q, i + Q.length); }
      }
      H.set("hy-set-q", new Highlight(...ranges));
    }

    // the words at the right end of a section's header (at the side): what is chosen in it --------------------------------------------
    const chosen = k => { const b = body.querySelector(`hy-segmented[data-set=${k}] > button.on`); return b ? (b.querySelector(".sp-pvl") || b).textContent.trim() : ""; };
    const onOf = (sel, ok = () => true) => { const s = [...body.querySelectorAll(sel)].filter(ok); return [s.filter(x => x.hasAttribute("checked")).length, s.length]; };
    const SUM = {
      profile: () => { const m = window.hyPeople && window.hyPeople.me(); return m ? m.name : T("No profile"); },
      team: () => T("Agents: {a} · team: {p}", { a: body.querySelectorAll(".hp-mine:not(.hp-idle)").length, p: body.querySelectorAll(".hp-person:not(.hp-off)").length }),
      appearance: () => [chosen("theme"), chosen("shape"), chosen("shadow")].filter(Boolean).join(" · "),
      board: () => { const g = chosen("grain"), d = body.querySelector("#dotsVis"); return g ? T("{grain} grain · {dots}% dots", { grain: g.toLowerCase(), dots: d ? d.value : "" }) : ""; },
      notifications: () => {
        const m = body.querySelector("hy-switch[data-mn-sw=mac]"); if (!m) return "";
        const [n, all] = onOf("hy-switch[data-mn-sw]", s => /^mac\.(?!bg$)/.test(s.dataset.mnSw));
        return m.hasAttribute("checked") ? T("{n} of {m} on", { n, m: all }) : T("Off");
      },
      plugins: () => { const [n, all] = onOf("hy-switch[data-pl-sw]"); return all ? T("{n} of {m} on", { n, m: all }) : ""; },
      storage: () => { const r = [...body.querySelectorAll("#hyStore .hs-row")].find(x => x.firstElementChild && x.firstElementChild.textContent === T("Boards"));
        return r && r.querySelector(":scope > b") ? `${T("Boards")} ${r.querySelector(":scope > b").textContent}` : ""; },
      interface: () => chosen("hideui") ? T("{hide} · key hints: {keys}", { hide: chosen("hideui"), keys: chosen("keyhint").toLowerCase() }) : "",
      performance: () => [body.querySelector("#engineSet:not([hidden])") ? chosen("engine") : "", chosen("lod")].filter(Boolean).join(" · "),
    };
    function sums() {
      if (!side()) return;
      body.querySelectorAll(".sw-sl .sw-sum").forEach(s => { const id = s.parentElement.dataset.for, t = id === "profile" ? SUM[id]() : cap(SUM[id]()); if (s.textContent !== t) s.textContent = t; });
    }
    ["hy-change", "change", "input"].forEach(t => body.addEventListener(t, () => requestAnimationFrame(sums)));
    // a module that draws its section again: the section keeps its state (and the search its rows)
    let queued = false;
    new MutationObserver(() => { if (queued) return; queued = true; queueMicrotask(() => { queued = false; if (!("swGone" in el.dataset)) paint(); else tag(); }); })
      .observe(body, { childList: true, subtree: true });

    const keepShut = () => store.set(SHUT, [...shut]);
    // a section's header to the top: measured by its first group (a header stuck at the top tells where it sticks, not where it stands)
    const scrollTo = l => {
      const g = [...body.querySelectorAll(`[data-sec="${l.dataset.for}"].sw-on`)].filter(x => x.getClientRects().length).sort((a, b) => a.style.order - b.style.order)[0];
      body.scrollTop += g ? g.getBoundingClientRect().top - body.getBoundingClientRect().top - l.offsetHeight : 0;
    };
    // a section: in the window it is the one shown; at the side it unfolds and comes to the top
    function go(id) {
      if (!NAME[id]) return;
      if (Q) { q.value = ""; Q = ""; }
      cur = id; store.set(SEC, id);
      if (side()) {
        shut.delete(id); keepShut(); paint();
        const l = body.querySelector(`.sw-sl[data-for="${id}"]`); if (l) scrollTo(l);
        return;
      }
      paint(); body.scrollTop = 0;
      body.classList.remove("sw-in"); void body.offsetWidth; body.classList.add("sw-in");
    }
    function search(v) { Q = String(v || "").trim().toLowerCase(); paint(); body.scrollTop = 0; }
    rail.addEventListener("click", e => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });
    // a section's header: at the side it folds or unfolds its section, in the window's search it goes there
    body.addEventListener("click", e => {
      const l = e.target.closest(".sw-sl"); if (!l || l.parentElement !== body) return;
      const id = l.dataset.for;
      if (!side()) { go(id); return; }
      if (Q) return;
      if (shut.has(id)) shut.delete(id); else shut.add(id);
      keepShut(); paint();
      if (!shut.has(id) && l.getBoundingClientRect().top < body.getBoundingClientRect().top + 1) scrollTo(l);
    });
    q.addEventListener("input", () => search(q.value));
    // the profile's face and name at the top of the rail (ui/people.js)
    function me() {
      const P = window.hyPeople, m = P && P.me(), av = el.querySelector(".sw-av"), nm = el.querySelector(".sw-mt b");
      const pic = m && ((P.people()[m.id] || {}).avatar || m.avatar);
      av.innerHTML = m && window.hyAvatarHTML ? window.hyAvatarHTML({ name: m.name, color: m.color, src: pic, size: 32 }) : ic("person", 18);
      nm.textContent = m ? m.name : T("Profile");
      sums();
    }
    addEventListener("hy-people", me); me();

    // open and close: the page's class «open»; the window grows in from 0.96 and fades, the side slides in from the right ---------------
    let shutT = 0, was = false;
    function sync() {
      const open = el.classList.contains("open"); if (open === was) return; was = open;
      clearTimeout(shutT); document.documentElement.classList.toggle("hy-sets-on", open);
      if (open) {
        mode(want());
        delete el.dataset.swGone; void el.offsetWidth; el.dataset.swShown = ""; full(); paint();
        requestAnimationFrame(() => { if (el.classList.contains("open")) q.focus({ preventScroll: true }); });
      } else {
        delete el.dataset.swShown; document.documentElement.classList.remove("hy-sets-dock");
        if (el.contains(document.activeElement)) document.activeElement.blur();
        shutT = setTimeout(() => { el.dataset.swGone = ""; }, still() ? 0 : 380);
      }
    }
    new MutationObserver(sync).observe(el, { attributes: true, attributeFilter: ["class"] });
    const close = () => { if (!el.classList.contains("open")) return; const b = document.getElementById("bset"); if (b) b.click(); else el.classList.remove("open"); };
    el.querySelector(".sw-veil").addEventListener("click", close);
    hd.addEventListener("click", e => {
      const a = e.target.closest("[data-sw-act]"); if (!a) return;
      if (a.dataset.swAct === "close") close(); else toggleMode();
    });
    hd.addEventListener("keydown", e => {   // Home's keys that are not upgraded
      const a = e.target.closest("[data-sw-act][role=button]"); if (!a || (e.key !== "Enter" && e.key !== " ")) return;
      e.preventDefault(); a.click();
    });
    // Esc closes it, unless something over it has the key (a plugin's «…» menu, a question, the picture being placed); at the side only
    // while the panel has the keyboard: the board beside it keeps its own Esc
    addEventListener("keydown", e => {
      if (e.key !== "Escape" || !el.classList.contains("open") || e.defaultPrevented || e.cancelBubble) return;
      if (document.querySelector(".hpl-menu, #hyCrop, #hyConfirm")) return;
      if (side() && !el.contains(e.target) && !el.contains(document.activeElement)) return;
      e.preventDefault(); e.stopPropagation();
      if (e.target === q && q.value) { q.value = ""; search(""); return; }   // the first Esc clears the search
      close();
    }, true);
    // the board's keys wait while a setting has the keyboard (N, P, the arrows on a choice)
    el.addEventListener("keydown", e => { if (e.key !== "Escape") e.stopPropagation(); });

    // resize: the window by an edge or a corner (the edge follows the pointer, the opposite one moves as much the other way: it stays in the
    // middle); the side by its left edge, its right edge stays
    box.addEventListener("pointerdown", e => {
      const h = e.target.closest(".sw-rz"); if (!h || e.button !== 0) return;
      e.preventDefault(); h.setPointerCapture(e.pointerId);
      const d = h.dataset.rz, R = el.getBoundingClientRect(), cx = R.left + R.width / 2, cy = R.top + R.height / 2, r0 = box.getBoundingClientRect();
      const S = side();
      let w = r0.width, ht = r0.height;
      box.classList.add("sw-sizing");
      const move = ev => {
        if (S) { w = Math.max(SW_MIN, Math.min(sideMax(), r0.right - ev.clientX)); setSide(w); if (o.fit) o.fit(); heads(); return; }
        if (/[ew]/.test(d)) w = Math.max(Math.min(MIN_W, R.width), Math.min(R.width, 2 * Math.abs(ev.clientX - cx)));
        if (/^[ns]/.test(d)) ht = Math.max(Math.min(MIN_H, R.height), Math.min(R.height, 2 * Math.abs(ev.clientY - cy)));
        setSize(w, ht);
      };
      const up = () => {
        h.removeEventListener("pointermove", move); h.removeEventListener("pointerup", up); h.removeEventListener("pointercancel", up);
        box.classList.remove("sw-sizing");
        if (S) { store.set(SIDE_W, Math.round(w)); if (o.fit) o.fit(); return; }
        full();
        store.set(SIZE, box.classList.contains("sw-full") ? { full: true, before: { w: Math.round(r0.width), h: Math.round(r0.height) } } : { w: Math.round(w), h: Math.round(ht) });
        if (box.classList.contains("sw-full")) setSize(1e5, 1e5);   // the whole window, also when the window grows later
        if (o.fit) o.fit();
      };
      h.addEventListener("pointermove", move); h.addEventListener("pointerup", up); h.addEventListener("pointercancel", up);
    });
    // a double click on the window's title: the whole window, again: the size before (or the first one)
    hd.addEventListener("dblclick", e => {
      if (side() || e.target.closest("[data-sw-act]")) return;
      const s = store.get(SIZE) || {};
      if (box.classList.contains("sw-full")) { const b = s.before || {}; setSize(b.w, b.h); store.set(SIZE, b.w ? b : {}); }
      else { const b = tw ? { w: Math.round(tw), h: Math.round(th) } : {}; setSize(1e5, 1e5); store.set(SIZE, { full: true, before: b }); }
      setTimeout(() => o.fit && o.fit(), 420);
    });

    mode(want()); paint();
    return { body, go, search, sync, sums, side, el };
  }
  window.hySetWin = { build, SECS };
})();
