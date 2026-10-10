// The Library beside the board, round 15 (owner 2026-10-09, ♥ on Concepts/html/editors-concepts/r15/r15-library.html; his notes on rounds 14
// and 15: «dark panel skin like History», no Pages block in the library, compact width folds the folders into the crumb, search with one
// Filter button). The look is ui/libpanel.css; this file adds the parts the page did not have and stacks the layers over the panel's top:
//   - the header «Library 16» and, in the search, ⌘F and the one Filter button (in the old dock, header.hy-dock, now the panel's top)
//   - «Folders 6» over the tree with its fold button, which puts the folders into the path (v2.html toggleTree)
//   - the Filter button opens the app's filter window (v2.html #tfPanel) under the search; filters on, it shows them as the app did (its ink
//     plate and the count). r15 draws the button closed only; older rounds' states are not followed (owner 2026-10-10)
//   - lay(): the search, the folders (a column, a section or a well under the path) and the path, one under the other;
//     the list's padding starts under them. The width decides the form (v2.html renderFolders): wide ≥ 480 px, regular ≥ 280, compact below.
// v2.html calls hyLibPanel.sync(root) after each drawing of the folders and hyLibPanel.placeTF() when it places the filter window.
(() => {
  if (window.hyLibPanel) return;
  const FOLD = 280, WIDE = 480, GAP = 6;
  const $ = s => document.querySelector(s), t = (s, o) => (window.T ? window.T(s, o) : s);
  const ic = (n, s = 14, w = 1.9) => (window.hyIcon ? window.hyIcon(n, s, w) : "");
  const on = () => { const b = document.body; return b.classList.contains("cv-on") && !b.classList.contains("cv-only"); };
  let head, tail, btn, fold, ready = false, raf = 0, last = { n: 0, folders: 0 };

  function build() {
    const dock = $("header.hy-dock"), q = $("#q"); if (!dock || !q) return false;
    head = document.createElement("div"); head.className = "lph"; dock.prepend(head);
    tail = document.createElement("span"); tail.className = "lpf";
    tail.innerHTML = `<span class="lpk" aria-hidden="true">⌘F</span>`
      + `<button type="button" class="lfb" id="lfbtn" aria-expanded="false">${ic("filter", 14, 2)}<span></span><hy-badge count="0"></hy-badge></button>`;
    dock.append(tail); btn = tail.querySelector("#lfbtn"); btn.querySelector("span").textContent = t("Filter"); btn.title = t("Filter");
    // «Folders 6» and the fold button, over the tree (the drawer keeps its folder search for the wide column)
    fold = document.createElement("div"); fold.className = "lfh";
    fold.innerHTML = `<span></span><em></em><span class="sp"></span><button type="button" data-lpfold>${ic("collapse", 12, 2)}</button>`;
    fold.querySelector("span").textContent = t("Folders");
    const fb = fold.querySelector("button"); fb.title = t("Fold into the path"); fb.setAttribute("aria-label", fb.title);
    const nav = $("#fnav"); if (nav) nav.before(fold);
    return true;
  }

  // ---------- the form and the stack ----------
  function form() {
    const b = document.body, w = $("main").getBoundingClientRect().width;
    return b.classList.contains("fdock") ? "wide" : b.classList.contains("fsect") ? "regular" : w < FOLD ? "compact" : "folded";
  }
  function lay() {
    raf = 0;
    const b = document.body, m = $("main"); if (!ready || !m) return;
    const tf = $("#tfPanel"), inside = on();
    if (tf) tf.classList.toggle("lp-in", inside);
    if (!inside) { m.style.paddingTop = ""; return; }
    const r = m.getBoundingClientRect(), W = r.width, f = form();
    b.classList.toggle("lp-cmp", W < FOLD);
    const qr = Math.ceil(tail.getBoundingClientRect().width) + 10; if (qr > 10) document.documentElement.style.setProperty("--lp-qr", qr + "px");
    let y = r.top + 1 + $("header.hy-dock").offsetHeight;
    if (tf && !tf.hidden) {   // the app's filter window, under the search, over the folders and the pictures
      const w = Math.min(620, W - 24);
      Object.assign(tf.style, { top: y + 8 + "px", left: r.left + (W - w) / 2 + "px", width: w + "px", maxHeight: Math.max(200, r.bottom - y - 20) + "px" });
    }
    const d = $("#fdrawer"), bar = $("#fbar"), shown = d && d.classList.contains("open");
    let pad;
    if (f === "wide") {
      d.style.top = y + "px"; d.style.maxHeight = ""; bar.style.top = y + "px"; pad = y - r.top + 34 + 4;
    } else if (f === "regular") {
      d.style.top = y + "px"; d.style.maxHeight = Math.max(120, Math.round((r.bottom - y) * .5)) + "px"; y += shown ? d.offsetHeight : 0;
      bar.style.top = y + "px"; pad = y - r.top + 30 + 4;
    } else {
      bar.style.top = y + "px"; y += 34 + 4;
      if (shown) { d.style.top = y + "px"; d.style.maxHeight = Math.max(120, Math.round((r.bottom - y) * .5)) + "px"; y += d.offsetHeight + 8; }
      pad = y - r.top;
    }
    m.style.paddingTop = Math.round(pad) + "px";
    // narrower than wide, the pictures fill the row at about the slider's size (the drawing's 3 columns at 320 px, 2 at 248)
    const fill = f !== "wide" && !b.classList.contains("lrows"), ls = parseFloat(getComputedStyle(b).getPropertyValue("--ls")) || 150;
    const inner = W - 2 - 20, cols = Math.max(2, Math.round((inner + GAP) / (ls + GAP)));
    if (b.classList.contains("lfill") !== fill || b.style.getPropertyValue("--lcols") !== String(cols)) {
      b.classList.toggle("lfill", fill); b.style.setProperty("--lcols", cols); if (typeof sizeGrids === "function") sizeGrids();
    }
  }
  const soon = () => { if (!raf) raf = requestAnimationFrame(lay); };

  // the header's count, the search's words, the section's count (v2.html renderFolders gives the tree's root)
  function sync(root) {
    if (root) last = { n: root.n || 0, folders: root.kids ? root.kids.size : 0 };
    if (!ready) return;
    head.innerHTML = ""; head.append(t("Library")); const em = document.createElement("em"); em.textContent = window.T && T.num ? T.num(last.n) : last.n; head.append(em);
    const q = $("#q"), w = $("main").getBoundingClientRect().width;
    if (q) q.placeholder = on() && w >= FOLD ? t("Search {n} items", { n: last.n }) : t("Search");
    fold.querySelector("em").textContent = last.folders;
    paint(); soon();
  }

  // ---------- the Filter button: the app's filter window ----------
  const count = () => +($("#tfN") && $("#tfN").getAttribute("count")) || 0;
  const tfOpen = () => !!$("#tfPanel") && !$("#tfPanel").hidden;
  function paint() {
    if (!ready) return;
    const n = count(), o = tfOpen();
    btn.classList.toggle("act", n > 0); btn.classList.toggle("open", o); btn.setAttribute("aria-expanded", o);
    btn.querySelector("hy-badge").setAttribute("count", n);
    btn.title = n ? t("Filters on: {n}", { n }) : t("Filter");
  }
  function press() { $("#tfBtn").click(); }

  function start() {
    if (ready || !(ready = build())) return;
    btn.addEventListener("click", e => { e.stopPropagation(); press(); });
    document.addEventListener("click", e => {
      if (e.target.closest("[data-lpfold]")) { e.stopPropagation(); if (typeof toggleTree === "function") toggleTree(false); }
    }, true);
    // ⌘F: the library's search, opening the library if it is closed (the board's page asks by message, canvas.html)
    // not while the viewer is open (P4 B-14): the search hides behind it and the next letters would filter the library, not rate the picture
    const find = () => {
      const v = document.getElementById("viewer"); if (v && v.classList.contains("open")) return;
      if (!document.body.classList.contains("cv-on")) { $("#q").focus(); return; }
      if (!on() && typeof setView === "function") setView("panel");
      setTimeout(() => { const q = $("#q"); q.focus(); q.select(); }, on() ? 0 : 380);
    };
    document.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && (e.code === "KeyF" || ["f", "F", "а", "А"].includes(e.key))) { e.preventDefault(); find(); }
    }, true);
    addEventListener("message", e => { if (e.origin === location.origin && e.data && e.data.type === "libSearch") find(); });
    // Esc in the search: its words go first, a second Esc gives the keys back to the board (P4 B-55: the search kept them)
    $("#q").addEventListener("keydown", e => {
      if (e.key !== "Escape" || e.isComposing) return; e.preventDefault(); e.stopPropagation();
      if ($("#q").value) { $("#q").value = ""; if (typeof render === "function") render(); } else if (document.body.classList.contains("cv-on")) focusBoard(); else $("#q").blur();
    });
    // the filter window closes on Esc and on a click on the board (this page loses the focus), as the view's popover (P4 B-19); Esc in its
    // tag form leaves the field first
    document.addEventListener("keydown", e => {
      if (e.key !== "Escape" || $("#tfPanel").hidden) return; e.preventDefault(); e.stopImmediatePropagation();
      if (window.hyTyping && hyTyping(e)) hyTyping.toBoard(); else tfClose();
    }, true);
    addEventListener("blur", tfClose);
    // the stack follows the panel, the filters and the folders
    const ro = new ResizeObserver(soon);
    ["main", "header.hy-dock", "#fdrawer", "#fbar", "#tfPanel"].forEach(s => { const el = $(s); if (el) ro.observe(el); });
    new MutationObserver(() => { paint(); soon(); }).observe($("#tfPanel"), { attributes: true, attributeFilter: ["hidden"] });
    const n = $("#tfN"); if (n) new MutationObserver(paint).observe(n, { attributes: true, attributeFilter: ["count", "hidden"] });
    new MutationObserver(() => { soon(); sync(); }).observe(document.body, { attributes: true, attributeFilter: ["class", "style"] });
    addEventListener("resize", soon);
    sync(); lay();
  }
  function tfClose() { const p = $("#tfPanel"); if (!p || p.hidden) return false; p.hidden = true; $("#tfBtn").setAttribute("aria-expanded", false); return true; }
  // the keys to the board's frame (P4 B-34, B-55: ⌘M or a second Esc in the search left them nowhere)
  function focusBoard() { const f = $("#cvFrame"), a = document.activeElement; if (a && a !== document.body && a !== f && a.blur) a.blur(); try { f.focus(); f.contentWindow.focus(); } catch {} }
  // v2.html's placeTF: beside the board the window is the panel's own, under the search
  function placeTF() { if (!ready || !on()) return false; $("#tfPanel").classList.add("lp-in"); lay(); return true; }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  window.hyLibPanel = { sync, lay, placeTF, form, press, tfClose, focusBoard, FOLD, WIDE, get ready() { return ready; } };
})();
