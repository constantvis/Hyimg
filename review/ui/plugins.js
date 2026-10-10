// Settings › Plugins (owner 2026-10-07: «Хочу, чтобы в настройках было видно, какие плагины подключены, добавить новый плагин ... в
// процессе работы отключить какой-то плагин, и он отключался ... В настройках включить, выключить и посмотреть»). A section of the shared
// settings panel (ui/setpanel.js), the same on Home and on every board: a row a plugin with its name, version, what it does (the
// manifest's description in the app's language when it has one) and its folder (a click shows it in Finder, in a plain browser copies its
// path), an on/off switch and «…» with Remove; «Add plugin…» under them.
//
// Where the list comes from: a board asks its server (GET /api/plugins/all, review/plugins_admin.py), Home asks the app ({action:
// "plugins", op: "list"}, the app runs plugins_admin.py) and gets window.hyimgPlugins(d) back. On and off is the app's setting
// cv.plugoff, the names turned off: Home sends it through the app like its other settings; a board writes it to its server and tells the
// app, which makes the other boards read it again. Each board then takes it itself (ui/plugins-board.js): it reloads without the plugin,
// or, while the person is inside that plugin's editor, waits and says so on the row.
// Add (a folder panel, the manifest checked, a link made) needs the app; in a plain browser it is grey with the reason. Remove takes
// only the link away, asked first.
(() => {
  if (window.hyPlugins) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const FILE = location.protocol === "file:";
  const wk = (() => { try { const w = window.top.webkit || window.webkit; return w && w.messageHandlers && w.messageHandlers.hyimg; } catch { return null; } })();
  const cef = /HyimgCEF/.test(navigator.userAgent), IN_APP = !!wk || cef;
  const toApp = m => { if (wk) { wk.postMessage(m); return true; } if (cef) { console.log("HYIMG_MSG:" + JSON.stringify(m)); return true; } return false; };
  const T = (k, v) => window.T ? window.T(k, v) : String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? String(v[x]) : m));
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const say = (m, k) => (window.hyToast || (() => {}))(m, k);
  const icon = (n, s, w) => (window.hyIcon ? window.hyIcon(n, s, w) : "");
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = new URL("plugins.css", SRC).href; document.head.appendChild(css);
  const S = { list: null, root: "", busy: false };
  // a board upgrades the primitives (ui/hy/index.js); Home links their CSS only, so the real control inside is written here
  const UP = n => !!(window.customElements && customElements.get(n));
  // where the settings' sections stand: the settings window's body (ui/settings-win.js, hySetPanel.body()), else the page's #sets
  const host = () => (window.hySetPanel && window.hySetPanel.body()) || document.getElementById("sets");

  function got(d) {
    if (!d) return;
    S.busy = false;
    if (d.error) say(d.op === "remove" ? T("Not removed: {why}", { why: d.error }) : T("Not added: {why}", { why: d.error }), "error");
    if (Array.isArray(d.plugins)) { S.list = d.plugins; S.root = d.root || ""; }
    if (d.added && !d.error) say(T("«{name}» added", { name: d.title || d.added }), "success");
    if (d.removed && !d.error) say(T("«{name}» removed", { name: d.removed }), "success");
    paint();
  }
  window.hyimgPlugins = got;
  function load() {
    if (FILE) { toApp({ action: "plugins", op: "list" }); return; }
    fetch("/api/plugins/all", { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(got).catch(() => {});
  }

  // on and off: the setting cv.plugoff, the names turned off ---------------------------------------------------------------------
  function setOn(name, on) {
    const off = new Set((S.list || []).filter(p => p.off).map(p => p.name));
    if (on) off.delete(name); else off.add(name);
    S.list = (S.list || []).map(p => p.name === name ? { ...p, off: !on } : p);
    const v = [...off].sort().join(",") || null, change = { "cv.plugoff": v };
    paint();
    if (FILE) { toApp({ action: "settings", change }); return; }   // Home: as its other settings; the app makes the boards read the file
    fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(change) })
      .then(r => { if (!r.ok) throw new Error(r.status); toApp({ action: "settings", change }); if (window.hyPlugBoard) window.hyPlugBoard.apply(); })
      .catch(() => { say(T("Not saved: {why}", { why: T("the server did not answer") }), "error"); load(); });
  }

  // what the person sees ------------------------------------------------------------------------------------------------------------
  const btn = (attrs, words, o = {}) => `<hy-button size="s"${o.variant ? ` variant="${o.variant}"` : ""} ${attrs}${o.off ? " disabled" : ""}>`
    + (UP("hy-button") ? (o.ic || "") + esc(words) : `<button type="button"${o.off ? " disabled" : ""}>${o.ic || ""}${esc(words)}</button>`) + "</hy-button>";
  const more = p => { const l = T("More for {name}", { name: p.title }); return `<hy-icon-button size="s" icon="more" label="${esc(l)}" data-pl-more>`
    + (UP("hy-icon-button") ? "" : `<button type="button" aria-label="${esc(l)}" title="${esc(l)}">${icon("more", 14, 2)}</button>`) + "</hy-icon-button>"; };
  const sw = p => { const l = T("Turn {name} on or off", { name: p.title }); return `<hy-switch variant="well" data-pl-sw${p.off ? "" : " checked"} label="${esc(l)}">`
    + (UP("hy-switch") ? "" : `<input type="checkbox" class="hy-in" role="switch" aria-label="${esc(l)}"${p.off ? "" : " checked"}>`) + "</hy-switch>"; };
  // round 15's LED (owner 2026-10-09, r15-micro.html: «green for «running» … in Settings, a ring for «off»»): on and working, or not
  const led = p => { const on = !p.off && !p.error, l = esc(T(on ? "Running" : "Off")); return `<hy-led state="${on ? "ok" : "off"}" role="img" aria-label="${l}" title="${l}"></hy-led>`; };
  const folderTip = () => IN_APP || FILE ? T("Show in Finder") : T("Copy the path");
  function rowHtml(p) {
    const pend = window.hyPlugBoard ? window.hyPlugBoard.pending(p.name) : "";
    const tail = String(p.folder || "").split("/").filter(Boolean).pop() || p.folder || "";
    return `<div class="hpl-row${p.error ? " hpl-bad" : p.off ? " hpl-off" : ""}" data-pl="${esc(p.name)}"><div class="hpl-txt">`
      + `<div class="hpl-top">${led(p)}<span class="hpl-name">${esc(p.title || p.name)}</span>${p.version ? `<span class="hpl-ver">${esc(p.version)}</span>` : ""}</div>`
      + (p.error ? `<div class="hpl-desc hpl-err">${esc(T(p.error))}</div>` : p.description ? `<div class="hpl-desc" title="${esc(p.description)}">${esc(p.description)}</div>` : "")
      + `<div class="hpl-dir">${btn(`data-pl-dir title="${esc(folderTip() + ": " + (p.folder || ""))}"`, tail, { variant: "ghost", ic: icon("folder", 12, 2) })}</div>`
      + (pend ? `<div class="hy-hint hpl-pend">${esc(pend)}</div>` : "")
      + `</div><span class="hpl-ctl">${more(p)}${p.error ? "" : sw(p)}</span></div>`;
  }
  function section() {
    const sets = host(); if (!sets) return null;
    let el = document.getElementById("hyPlugSet");
    if (!el) {
      el = document.createElement("section"); el.id = "hyPlugSet"; el.className = "sp-g hpl"; el.setAttribute("aria-label", T("Plugins"));
      el.addEventListener("click", click); el.addEventListener("change", change); el.addEventListener("hy-change", change);
    }
    // after the shared rows (ui/setpanel.js), before Storage (ui/storage.js)
    const sp = sets.querySelector(":scope > .sp");
    if (sp && el.previousElementSibling !== sp) sp.after(el); else if (!sp && !el.isConnected) sets.appendChild(el);
    return el;
  }
  function paint() {
    const el = section(); if (!el) return;
    const rows = (S.list || []).slice().sort((a, b) => String(a.title || a.name).localeCompare(String(b.title || b.name)));
    const add = IN_APP || FILE ? "" : ` title="${esc(T("Only in the Mac app"))}"`;
    let h = `<div class="sh">${esc(T("Plugins"))}</div>`;
    h += S.list == null ? `<div class="hpl-none">${esc(T("Measuring…"))}</div>` : rows.length ? rows.map(rowHtml).join("") : `<div class="hpl-none">${esc(T("No plugins"))}</div>`;
    h += `<div class="sp-row hpl-add">${btn(`data-pl-add${add}`, T("Add plugin…"), { off: !(IN_APP || FILE) || S.busy, ic: icon("plus", 13, 2) })}</div>`;
    h += `<div class="hy-hint">${T("A plugin is a folder with <b>manifest.json</b>. Off, <b>its cards stay</b> on the boards as pictures")}</div>`;
    if (el._h !== h) { el.innerHTML = h; el._h = h; }
  }

  // the row's actions -------------------------------------------------------------------------------------------------------------
  const rowOf = e => { const r = e.target.closest("[data-pl]"); return r && (S.list || []).find(p => p.name === r.dataset.pl); };
  function change(e) {
    const s = e.target.closest("hy-switch[data-pl-sw]"); if (!s) return;
    if (e.type === "change" && UP("hy-switch")) return;   // an upgraded switch says hy-change
    const on = e.type === "hy-change" ? !!(e.detail && e.detail.checked) : e.target.checked;
    s.toggleAttribute("checked", on);
    const p = rowOf(e); if (p) setOn(p.name, on);
  }
  function click(e) {
    const p = rowOf(e);
    if (e.target.closest("[data-pl-add]")) { if (!S.busy && (IN_APP || FILE) && toApp({ action: "plugins", op: "add" })) S.busy = true; return; }
    if (!p) return;
    if (e.target.closest("[data-pl-dir]")) return reveal(p);
    if (e.target.closest("[data-pl-more]")) { e.stopPropagation(); menu(e.target.closest("[data-pl-more]"), p); }
  }
  function reveal(p) {
    if (toApp({ action: "plugins", op: "reveal", path: p.folder })) return;
    try { navigator.clipboard.writeText(p.folder).then(() => say(T("Path copied"), "success"), () => say(p.folder, "info")); } catch { say(p.folder, "info"); }
  }
  // «…»: Show in Finder, Remove (grey with the reason for a plugin that is not a link of the plugins folder)
  let MENU = null;
  function closeMenu() { if (MENU) { MENU.remove(); MENU = null; } }
  function menu(at, p) {
    closeMenu();
    const why = !p.own ? T("It comes from HYIMG_PLUGINS, not from the plugins folder") : !p.link ? T("A folder, not a link: move it in Finder") : "";
    const m = document.createElement("div"); m.className = "hpl-menu"; m.setAttribute("role", "menu"); m.dataset.hymenu = "";
    m.innerHTML = window.hyMenuItem("data-m=dir", "folder", esc(folderTip()))
      + window.hyMenuItem("data-m=remove", "trash", esc(T("Remove…")), null, why ? window.hyMenuOff(why) : ' class="danger"');
    document.body.appendChild(m);
    const r = at.getBoundingClientRect();
    m.style.left = Math.max(8, Math.min(innerWidth - m.offsetWidth - 8, r.right - m.offsetWidth)) + "px";
    m.style.top = (r.bottom + 4 + m.offsetHeight > innerHeight - 8 ? r.top - 4 - m.offsetHeight : r.bottom + 4) + "px";
    m.addEventListener("click", ev => {
      ev.stopPropagation(); const b = ev.target.closest("button[data-m]"); if (!b || b.getAttribute("aria-disabled") === "true") return;
      closeMenu(); if (b.dataset.m === "dir") reveal(p); else remove(p);
    });
    MENU = m; requestAnimationFrame(() => m.classList.add("on"));
  }
  // a press on it is its own, not a click beside the settings panel (the board closes the panel on such a press, in its capture phase)
  addEventListener("pointerdown", e => { if (!MENU) return; if (e.target.closest(".hpl-menu")) e.stopPropagation(); else closeMenu(); }, true);
  addEventListener("keydown", e => { if (MENU && e.key === "Escape") { e.stopPropagation(); closeMenu(); } }, true);
  async function remove(p) {
    const o = { title: T("Remove «{name}»?", { name: p.title }), ok: T("Remove"), cancel: T("Cancel"),
      note: T("Only its link in the plugins folder goes. The plugin's own folder stays where it is") };
    if (FILE) { toApp({ action: "plugins", op: "remove", name: p.name, confirm: true, ...o }); return; }   // Home: the app asks with these words
    if (!window.hyConfirm) { try { await import(new URL("confirm.js", SRC).href); } catch {} }
    const yes = window.hyConfirm ? await new Promise(ok => window.hyConfirm({ ...o, icon: "trash", onOk: () => ok(true), onCancel: () => ok(false) })) : confirm(o.title);
    if (!yes) return;
    const d = await fetch("/api/plugins/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: p.name }) })
      .then(r => r.json()).catch(() => ({ error: T("the server did not answer") }));
    got({ op: "remove", ...d });
    toApp({ action: "plugins", op: "changed" });   // the app makes the other boards and Home look again
    if (!d.error && window.hyPlugBoard) window.hyPlugBoard.apply();
  }

  // the panel: the list is read when it opens --------------------------------------------------------------------------------------
  function watch() {
    const sets = document.getElementById("sets"); if (!sets) return;
    new MutationObserver(() => { if (sets.classList.contains("open")) { paint(); load(); } else closeMenu(); }).observe(sets, { attributes: true, attributeFilter: ["class"] });
    const body = host();
    new MutationObserver(() => { const el = document.getElementById("hyPlugSet"), sp = body.querySelector(":scope > .sp"); if (!el || (sp && el.previousElementSibling !== sp)) paint(); })
      .observe(body, { childList: true });
    paint();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch); else watch();
  window.hyPlugins = { load, paint, got, list: () => S.list };
})();
