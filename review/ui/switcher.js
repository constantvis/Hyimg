// ⌃Tab's cards, the switch between boards with its motion, the crumb's list of boards and the board's side of sleeping (owner
// 2026-10-08, «Вкладки со сном»: «Главное, чтобы таб еще с анимацией был: blur + scale down, и scale, когда released. При этом верхнюю
// панель можно сохранить и потом показывать, что мы переключились на другую страницу»). Loaded by the library page around a board
// (v2.html) and by Home (home.html); the app drives it (native/Switcher.swift, BoardSleep.swift):
//   hyimgSwitcher({open: true, boards, pick})   the cards over this page, its board blurred behind them and a little smaller
//   hyimgSwitcher({pick})                        another card picked (Tab, ⇧Tab, the arrows)
//   hyimgSwitcher({open: false, keep})           the cards go; keep: a switch follows, the veil stays for it
//   hyimgSwitchOut({name, state})                a board loads behind this one: the veil stays, the crumb says where we go with a ring,
//                                                the top row keeps working; null: back as it was (instant: at once, this page is behind)
//   hyimgSwitchWait(ms, token)                   the board switched to: it answers {action: "switchShown", drawn, token} once what is on
//                                                its screen is drawn, at most ms (5 s; ui/switchin.js), and the app brings it in; the
//                                                token says which wait it ends (a switch given up and made again asks again)
//   hyimgSwitchIn("prep"), hyimgSwitchIn("play")   the board switched to: under the veil and smaller, then scaling up into place
//   hyimgSwitchRestore({page, sel})              a woken board takes its selection back
//   hyimgBoards(cards)                           the open boards, for the crumb's list (hySwitchRows, asked by canvas.html)
//   hyimgSleepAsk(token)                         what keeps this board awake, answered {action: "sleepState", token, state}
// A card: {id, name, state: open | warm | sleeping | waking | loading | home, ago: seconds behind, covers: [the first frames' thumbs]}
(() => {
  if (window.hyimgSwitcher) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href, CSS = new URL("switcher.css", SRC).href;
  const MS = 350, EASE = "cubic-bezier(.32,.72,0,1)", SMALL = .96;
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const T = (k, v) => (window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m)));
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const ic = (name, size, line) => (window.hyIcon ? window.hyIcon(name, size, line) : "");
  const link = doc => {
    if (!doc || doc.querySelector(`link[href="${CSS}"]`)) return;
    const l = doc.createElement("link"); l.rel = "stylesheet"; l.href = CSS; (doc.head || doc.documentElement).appendChild(l);
  };
  link(document);
  const post = m => {
    try { if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.hyimg) { window.webkit.messageHandlers.hyimg.postMessage(m); return; } } catch {}
    if (/HyimgCEF/.test(navigator.userAgent)) console.log("HYIMG_MSG:" + JSON.stringify(m));
  };
  const frame = () => document.getElementById("cvFrame");
  const board = () => { try { const d = frame() && frame().contentDocument; return d && d.getElementById("stage") ? d : null; } catch { return null; } };
  // where the motion happens: the board (its stage holds the veil, its world scales) or Home (its columns)
  function place() {
    const d = board();
    if (d) return { doc: d, host: d.getElementById("stage"), big: d.getElementById("world"), home: false };
    const app = document.querySelector("body > .app");
    return app && !frame() ? { doc: document, host: document.body, big: app, home: true } : null;
  }
  function veil(P) {
    let v = P.doc.querySelector(".hysw-veil");
    if (v && v.parentNode !== P.host) { v.remove(); v = null; }
    if (!v) {
      link(P.doc); v = P.doc.createElement("div"); v.className = "hysw-veil" + (P.home ? " home" : "");
      v.innerHTML = `<div class="hysw-wake" role="status" aria-live="polite"></div>`;
      // the board under it takes nothing while it is on; a press beside the cards closes them
      v.addEventListener("pointerdown", e => { e.stopPropagation(); e.preventDefault(); if (OPEN) post({ action: "switchCancel" }); });
      ["wheel", "click", "dblclick", "contextmenu"].forEach(t => v.addEventListener(t, e => { e.stopPropagation(); e.preventDefault(); }, { passive: false }));
    }
    if (P.host.lastElementChild !== v) P.host.appendChild(v);   // last: over the board's own layers of the same height
    return v;
  }
  // the board a little smaller around the window's centre: scale and translate, the camera's own transform untouched
  let ANIM = null;
  function size(P, small, ms) {
    const el = P.big; if (!el) return;
    const w = P.doc.defaultView, cs = w.getComputedStyle(el), s0 = cs.scale === "none" ? 1 : parseFloat(cs.scale) || 1;
    const t0 = cs.translate === "none" ? "0px 0px" : cs.translate, s1 = small ? SMALL : 1;
    const [ox, oy] = cs.transformOrigin.split(" ").map(parseFloat), pr = el.offsetParent ? el.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
    const O = [pr.left + el.offsetLeft + (ox || 0), pr.top + el.offsetTop + (oy || 0)], C = [w.innerWidth / 2, w.innerHeight / 2];
    const t1 = small ? `${((1 - s1) * (C[0] - O[0])).toFixed(1)}px ${((1 - s1) * (C[1] - O[1])).toFixed(1)}px` : "0px 0px";
    if (ANIM) ANIM.cancel();
    if (!small && s0 === 1) { ANIM = null; return; }
    const a = ANIM = el.animate([{ scale: String(s0), translate: t0 }, { scale: String(s1), translate: t1 }], { duration: calm() ? 0 : ms, easing: EASE, fill: "forwards" });
    if (!small) a.finished.then(() => { if (ANIM === a) { a.cancel(); ANIM = null; settled(P); } }, () => {});
  }
  // the board's world its own size again: the bars over its selection are laid again (laid while it was smaller, they stood off it)
  const settled = P => { try { const w = P.doc.defaultView; if (!P.home && w.hyimgSwitchSettled) w.hyimgSwitchSettled(); } catch {} };
  function out(P, on, instant) {
    const v = veil(P);
    if (instant) v.classList.add("cut");
    v.classList.toggle("on", on);
    if (instant) { void v.offsetWidth; v.classList.remove("cut"); }
    size(P, on, instant ? 0 : MS);
    if (!on) v.querySelector(".hysw-wake").classList.remove("on");
  }

  // the cards
  let OPEN = false, CARDS = [], PICK = 0, PEND = null, LIST = [];
  const ago = s => (s < 60 ? T("switch::now") : s < 3600 ? T("{n} min", { n: Math.round(s / 60) }) : T("{n} h", { n: Math.round(s / 3600) }));
  const said = b => ({ open: T("board::Open"), warm: T("Warm · {ago}", { ago: ago(b.ago || 0) }), sleeping: T("Asleep · {ago}", { ago: ago(b.ago || 0) }),
    waking: T("Waking"), loading: T("board::Opening"), home: T("switch::All boards") })[b.state] || "";
  const dot = st => (st === "sleeping" ? `<i class="hysw-st sleeping">${ic("sleep", 12, 2.2)}</i>`
    : st === "waking" || st === "loading" ? '<i class="hysw-spin"></i>' : st === "home" ? "" : `<i class="hysw-st ${st}"></i>`);
  const pics = b => (b.covers || []).slice(0, 3).map(u => `<img src="${esc(u)}" alt="" draggable="false">`).join("")
    + (b.state === "sleeping" ? `<i class="hysw-moon">${ic("sleep", 26, 1.8)}</i>` : "");
  const named = b => (b.state === "home" ? T("switch::Home") : b.name);
  function overlay() {
    let o = document.querySelector(".hysw");
    if (o) return o;
    o = document.createElement("div"); o.className = "hysw"; o.setAttribute("role", "dialog"); o.setAttribute("aria-label", T("Open boards"));
    o.innerHTML = `<div class="hysw-box"><div class="hysw-strip" role="listbox"></div><div class="hy-hint hysw-hint"></div></div>`;
    const strip = o.querySelector(".hysw-strip");
    strip.addEventListener("error", e => { if (e.target.tagName === "IMG") e.target.remove(); }, true);   // a frame with no thumb yet
    strip.addEventListener("pointermove", e => { const c = e.target.closest(".hysw-card"); if (c && +c.dataset.i !== PICK) { PICK = +c.dataset.i; mark(); post({ action: "switchPick", i: PICK }); } });
    strip.addEventListener("click", e => { const c = e.target.closest(".hysw-card"); if (c) post({ action: "switchTo", to: c.dataset.id }); });
    document.body.appendChild(o);
    return o;
  }
  function draw() {
    const o = overlay();
    o.querySelector(".hysw-strip").innerHTML = CARDS.map((b, i) => `<button type="button" class="hysw-card st-${esc(b.state)}" role="option" data-i="${i}" data-id="${esc(b.id)}">`
      + `<span class="hysw-cv${b.state === "home" ? " home" : ""}">${b.state === "home" ? ic("home", 30, 1.6) : pics(b)}</span>`
      + `<span class="hysw-n">${dot(b.state)}<b>${esc(named(b))}</b></span><span class="hysw-s">${esc(said(b))}</span></button>`).join("");
    o.querySelector(".hysw-hint").innerHTML = T("Hold <b>⌃</b>, <b>Tab</b> to the next, release to open");
    mark(); void o.offsetWidth; o.classList.add("on");
  }
  function mark() {
    document.querySelectorAll(".hysw-card").forEach(c => { const on = +c.dataset.i === PICK; c.classList.toggle("on", on); c.setAttribute("aria-selected", String(on)); });
  }
  const hide = () => { const o = document.querySelector(".hysw"); if (o) o.classList.remove("on"); };
  window.hyimgSwitcher = o => {
    o = o || {};
    if (o.open === true) { CARDS = o.boards || []; PICK = o.pick || 0; OPEN = true; draw(); const P = place(); if (P) out(P, true); return true; }
    if (o.open === false) {
      OPEN = false; hide();
      const P = place(); if (P && !o.keep && !PEND) out(P, false);
      return true;
    }
    if (typeof o.pick === "number") { PICK = o.pick; mark(); }
    return true;
  };

  // the crumb while a board loads behind this one: its name and a ring; its width moves smoothly
  function crumb(d, t) {
    const c = d.getElementById("crumb"), b = d.getElementById("cProj"), n = d.getElementById("cProjName"); if (!c || !n || !b) return;
    const w0 = c.getBoundingClientRect().width;
    if (t) {
      if (!("hyswWas" in n.dataset)) n.dataset.hyswWas = n.textContent;
      n.textContent = t.name; c.classList.add("hysw-pend");
      if (!b.querySelector(".hysw-spin")) b.insertAdjacentHTML("beforeend", '<i class="hysw-spin" aria-hidden="true"></i>');
    } else {
      if ("hyswWas" in n.dataset) { n.textContent = n.dataset.hyswWas; delete n.dataset.hyswWas; }
      c.classList.remove("hysw-pend"); b.querySelectorAll(".hysw-spin").forEach(x => x.remove());
    }
    const w1 = c.getBoundingClientRect().width;
    if (Math.abs(w1 - w0) > 1 && !calm()) c.animate([{ width: w0 + "px" }, { width: w1 + "px" }], { duration: 300, easing: EASE });
  }
  window.hyimgSwitchOut = (t, instant) => {
    const P = place(); PEND = t || null;
    if (!P) return false;
    if (!P.home) crumb(P.doc, PEND);
    const w = veil(P).querySelector(".hysw-wake");
    if (PEND) {
      w.innerHTML = (PEND.state === "sleeping" ? ic("sleep", 14, 2.2) : '<i class="hysw-spin"></i>')
        + `<span>${esc(T(PEND.state === "sleeping" ? "Waking “{name}”" : "Opening “{name}”", { name: PEND.name }))}</span>`;
      out(P, true); w.classList.add("on");
    } else {
      if (instant) { OPEN = false; hide(); }
      if (!OPEN) out(P, false, !!instant);
    }
    return true;
  };
  // a page that loaded behind waited for an entrance (canvas.html preintro, the library page's cv-wait): it comes quietly, its row in place
  // and its loading steps done (owner 2026-10-08: «Library: 222 frames, drawing the board» stayed over the board after a switch)
  function reveal() {
    const d = board(), w = d && d.defaultView;
    if (w && w.hyimgQuietIn) w.hyimgQuietIn(); else if (d) d.documentElement.classList.remove("preintro", "hy-open");
    document.documentElement.classList.remove("cv-wait", "lib-wait");
  }
  // the board switched to comes in drawn, not half empty with its pictures on their way (owner 2026-10-08, a woken board at 23 %): the board
  // in front keeps its place meanwhile, with «Waking “name”»
  window.hyimgSwitchWait = (ms = 5000, token) => {
    let w = null; try { w = frame().contentWindow; } catch {}
    const drawn = w && w.hyimgViewDrawn ? w.hyimgViewDrawn(ms) : Promise.resolve(true);
    drawn.catch(() => false).then(ok => post({ action: "switchShown", drawn: !!ok, ...(token == null ? {} : { token }) }));
    return true;
  };
  window.hyimgSwitchIn = phase => {
    const P = place(); if (!P) return false;
    if (phase === "prep") { reveal(); OPEN = false; hide(); PEND = null; if (!P.home) crumb(P.doc, null); out(P, true, true); return true; }
    out(P, false);
    return true;
  };
  window.hyimgSwitchRestore = r => { try { const w = frame().contentWindow; if (r && Array.isArray(r.sel) && w.hyimgSelect) w.hyimgSelect(r.sel); } catch {} return true; };

  // the crumb's list: the open boards first in the menu of the board's name (canvas.html asks parent.hySwitchRows)
  window.hyimgBoards = list => { LIST = Array.isArray(list) ? list : []; return true; };
  window.hySwitchRows = doc => {
    const L = LIST.filter(b => b.state !== "home"); if (L.length < 2 || !window.hyMenuItem) return "";
    link(doc);
    return `<div class="hysw-mh">${esc(T("Open boards"))}</div>` + L.map(b => window.hyMenuItem(
      `data-act="switchTo" data-to="${esc(b.id)}" class="hysw-row st-${esc(b.state)}"${b.state === "open" ? ' aria-current="true"' : ""}`,
      `<span class="hysw-th">${pics(b)}</span>`, `<span class="hysw-rn">${dot(b.state)}${esc(b.name)}</span><span class="hysw-rs">${esc(said(b))}</span>`)).join("")
      + `<div class="sep"></div>`;
  };

  // what keeps this board awake: an edit not saved or under way, a studio, a render or an upload, a video playing
  window.hyimgSleepAsk = token => {
    let st = { unsaved: false, editing: false, studio: "", busy: [], video: false };
    try { const w = frame().contentWindow; if (w && w.hyimgSleepState) st = { ...st, ...w.hyimgSleepState() }; else st.unsaved = true; } catch { st.unsaved = true; }
    try { st.video = [...(board() || document).querySelectorAll("video")].some(v => !v.paused && !v.ended); } catch {}
    // the library page's own saves (v2.html): a verdict or an answer that did not reach the server
    try { if ((typeof failedFeedback !== "undefined" && failedFeedback.size) || (typeof failedAnswers !== "undefined" && failedAnswers.size)) st.unsaved = true; } catch {}
    post({ action: "sleepState", token, state: st });
    return true;
  };
})();
