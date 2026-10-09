// Links that open the app (owner 2026-10-07: «Можно ли сделать ссылку, которую нажимаешь, и открывается приложение? Сейчас открывается
// браузер с этой вкладкой ... При этом чтобы оставалась возможность классической ссылки»). Both kinds of link stay:
//   hyimg://board/<board id>?page=<page>&obj=<id,id>&at=<x,y,z>   opens Hyimg on that board (native/Links.swift validates, LinkRouting.swift acts)
//   http://127.0.0.1:<port>/?view=canvas&page=…&obj=…              the board in a browser, as before
// The board's id is the one in its folder (<state>/board.json, GET /api/health boardId; owner 2026-10-08: two Macs on one Dropbox account,
// each with its own catalog), else its id in the app's catalog (projectId), never the port, which changes between runs. The app's link
// adds dir, the board's folder relative to the Dropbox root, so the other Mac can offer a board it has not added yet (native/BoardIdentity.swift).
//
// This file, in the library page (v2.html, the window's page) and the board (canvas.html, in its frame):
//   hyLink.app(params) / hyLink.browser(params)   the two links of {page, obj, at}
//   hyLink.items(kind) / hyLink.copy(act, params)  the board's «Copy as ›»: the app's link first, the browser's as before, the same for the view
//   window.hyimgGo({page, obj, at})               the app hands a link to a board that is already drawn: the page switches, the objects are
//                                                 selected and centred as ?obj= does on load (canvas.html openLink)
//   the plate «Open in Hyimg» · «Stay in browser» on top of a board opened in a normal browser (never inside the app, never in an
//   automated browser unless the address says ?applink=1); with the app's setting «Open board links in the app» (cv.applinks = "1") the
//   page goes to Hyimg by itself as it opens. ?stay=1 (the app's View › Open in Browser) and «Stay in browser» keep this tab in the browser.
(() => {
  if (window.hyLink) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const T = (k, v) => (window.T ? window.T(k, v) : k);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const TOP = (() => { try { return window.top === window; } catch { return false; } })();
  const IN_APP = /HyimgCEF/.test(navigator.userAgent)
    || (() => { try { return !!(window.top.webkit && window.top.webkit.messageHandlers && window.top.webkit.messageHandlers.hyimg); } catch { return false; } })();
  const ID = /^[A-Za-z0-9_-]{1,64}$/, CAM = /^-?[\d.]+,-?[\d.]+,[\d.]+$/, UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  // a folder relative to the Dropbox root, as Links.swift accepts it: parts without «.», «..», empty ones or control characters
  const DIR = s => typeof s === "string" && s.length > 0 && s.length <= 1024 && s.split("/").every(p => p && p !== "." && p !== ".." && !/[\x00-\x1f\x7f]/.test(p));
  const Q = new URLSearchParams(location.search);
  let project = "", dir = "";   // this board's id (its folder's, else the catalog's); "" for a server outside both (a test, one started by hand)
  const ready = fetch("/api/health", { cache: "no-store" }).then(r => (r.ok ? r.json() : {}))
    .then(j => { const id = j.boardId || j.projectId || ""; project = UUID.test(id) ? id.toLowerCase() : ""; dir = DIR(j.dir) ? j.dir : ""; return project; })
    .catch(() => "");

  // only the link's own parameters, each checked as the app checks it (Links.swift)
  function clean(p) {
    const o = {}, obj = String(p.obj || "").split(",").filter(x => ID.test(x));
    if (p.page && ID.test(p.page)) o.page = p.page;
    if (obj.length) o.obj = obj.join(",");
    if (p.at && CAM.test(p.at)) o.at = p.at;
    return o;
  }
  const qs = o => new URLSearchParams(o).toString().replace(/%2C/g, ",");
  const app = p => {
    if (!project) return "";
    const q = [qs(clean(p)), dir && "dir=" + dir.split("/").map(encodeURIComponent).join("/")].filter(Boolean).join("&");
    return `hyimg://board/${project}` + (q ? "?" + q : "");
  };
  const browser = p => `${location.origin}/?${qs({ view: "canvas", ...clean(p) })}`;
  const here = () => (typeof BOARD === "string" ? BOARD : Q.get("page") || "");   // the board's open page (canvas.html BOARD)

  // «Copy as ›» on the board: the app's link first (owner 2026-10-07), the browser's as before; kind says what the link is to
  function items(kind) {
    const off = project ? "" : hyMenuOff(T("This board is not in the app's catalog"));
    return [hyMenuItem(`data-act="applink"${off ? "" : ` title="${esc(kind)}"`}`, "open", T("App link"), null, off),
      hyMenuItem(`data-act="link" title="${esc(kind)}"`, "link", T("Browser link")),
      hyMenuItem('data-act="appview"', "open", T("App link to this view"), null, off), hyMenuItem('data-act="view"', "view", T("Browser link to this view"))].join("");
  }
  // the empty board's own two (its menu has no «Copy as ›»)
  const viewActs = () => [Object.assign(["appview", "open", T("Copy app link to this view")], project ? {} : { off: T("This board is not in the app's catalog") }),
    ["view", "view", T("Copy browser link to this view")]];
  async function copy(act, params) {
    const toApp = act === "applink" || act === "appview", view = act === "view" || act === "appview";
    if (toApp && !project) await ready;
    const p = { page: here(), ...params }, text = toApp ? app(p) : typeof linkTo === "function" ? linkTo(params) : browser(p);
    if (!text) { if (window.toast) window.toast(T("This board is not in the app's catalog"), "error"); return; }
    const done = toApp ? (view ? T("App link to this view copied") : T("App link copied: it opens Hyimg on this object"))
      : view ? T("Link to this view copied") : T("Link copied: it opens and shows this object");
    if (typeof copyText === "function") copyText(text, done); else navigator.clipboard.writeText(text).catch(() => {});
  }

  // the app hands over a link (LinkRouting.swift deliver): the library page passes it to its board, the board goes there
  window.hyimgGo = async o => {
    o = o && typeof o === "object" ? o : {};
    if (typeof BOARD_READY === "undefined") {
      try { const f = document.getElementById("cvFrame"); if (f && f.contentWindow && f.contentWindow.hyimgGo) return f.contentWindow.hyimgGo(o); } catch {}
      return;
    }
    await BOARD_READY;
    // after its entrance, 3 s at most by the clock (a hidden window draws no frames, its entrance waits, its timers are slowed)
    for (const t0 = Date.now(); Date.now() - t0 < 3000 && document.documentElement.classList.contains("preintro");) await new Promise(r => setTimeout(r, 100));
    const p = clean({ page: o.page, obj: (o.obj || []).join(","), at: o.at });
    if (p.page && p.page !== BOARD && !FIXED) {
      await refreshPages();
      if (pages.some(x => x.id === p.page)) await switchPage(p.page); else toast(T("The linked page is not on this board"), "error");
    }
    LINK.at = p.at || null; LINK.obj = p.obj ? p.obj.split(",") : [];
    if (LINK.at || LINK.obj.length) openLink();
  };

  // the plate in a normal browser, on the window's page only
  const automated = navigator.webdriver && Q.get("applink") !== "1";
  const stay = () => { try { return Q.get("stay") === "1" || sessionStorage.getItem("hy.applink.stay") === "1"; } catch { return Q.get("stay") === "1"; } };
  const auto = () => { try { return localStorage.getItem("cv.applinks") === "1"; } catch { return false; } };
  // the app's link of what this page shows now: the board's page (it may have moved on since the address), the address's objects and camera
  function current() {
    let page = Q.get("page") || "";
    try { const f = document.getElementById("cvFrame"), h = f && f.contentWindow && f.contentWindow.hyLink; if (h) page = h.here() || page; } catch {}
    const same = !Q.get("page") || page === Q.get("page");
    return app({ page, obj: same ? Q.get("obj") : "", at: same ? Q.get("at") : "" });
  }
  // to the app: the browser asks macOS, which starts Hyimg with the link (a test sets window.hyAppOpenHook before the page and sees the link)
  function openApp(u) {
    if (!u) return;
    window.hyLink.opened = u;
    if (typeof window.hyAppOpenHook === "function") window.hyAppOpenHook(u); else location.href = u;
  }
  // the app's own mark, not a link arrow (owner 2026-10-08: «тут нужно логотип ставить, а не иконку»): native/assets/hyimg.svg drawn small
  // hy-allow-begin: icon-inline the app's logo, a picture in its own colours, not an icon
  const LOGO = `<svg class="hy-applink-logo" viewBox="48 48 928 928" aria-hidden="true"><clipPath id="hyAppLogoTile"><rect x="48" y="48" width="928" height="928" rx="208"/></clipPath>`
    + `<g clip-path="url(#hyAppLogoTile)"><rect x="48" y="48" width="928" height="928" rx="208" fill="#e92001"/>`
    + `<path d="M304 1000V584C432 516 504 414 512 240C520 414 592 516 720 584V1000Z" fill="#ffbc22"/>`
    + `<g fill="none" stroke="#111" stroke-width="28" stroke-linecap="round" stroke-linejoin="round">`
    + `<path d="M96 636C168 636 236 620 304 584C432 516 504 414 512 240C520 414 592 516 720 584C788 620 856 636 928 636"/>`
    + `<path d="M304 584V1000M720 584V1000"/></g></g></svg>`;
  // hy-allow-end
  function plate() {
    if (document.getElementById("hyAppPlate")) return;
    if (!document.querySelector('link[href$="ui/applink.css"]')) {
      const l = document.createElement("link"); l.rel = "stylesheet"; l.href = new URL("applink.css", SRC).href; document.head.appendChild(l);
    }
    const el = document.createElement("hy-plate"); el.id = "hyAppPlate"; el.setAttribute("kind", "capsule"); el.className = "hy-applink";
    el.setAttribute("role", "region"); el.setAttribute("aria-label", T("Open in Hyimg"));
    el.innerHTML = `<hy-button size="l" variant="solid" data-applink="open">${LOGO}${esc(T("Open in Hyimg"))}</hy-button>`
      + `<hy-button size="l" variant="ghost" data-applink="stay">${esc(T("Stay in browser"))}</hy-button>`;
    el.addEventListener("click", e => {
      const b = e.target.closest("[data-applink]"); if (!b) return;
      if (b.dataset.applink === "open") { openApp(current()); return; }
      try { sessionStorage.setItem("hy.applink.stay", "1"); } catch {}
      el.remove();
    });
    document.body.appendChild(el);
  }
  if (TOP && !IN_APP && !automated && !stay()) {
    ready.then(id => {
      if (!id) return;
      const go = () => { plate(); if (auto()) openApp(current()); };   // the setting: straight to the app, the plate stays for a second try
      if (document.body) go(); else addEventListener("DOMContentLoaded", go, { once: true });
    });
  }

  window.hyLink = { app, browser, items, viewActs, copy, here, ready, get project() { return project; }, inApp: IN_APP, opened: "" };
})();
