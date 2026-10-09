// The board's side of plugins as a whole (owner 2026-10-07: «отключить какой-то плагин, и он отключался. Естественно, если я работаю в
// этом плагине, выхожу, и он потом отключается»). canvas.html calls init() before it loads the plugins, wrap(p) for each plugin's
// register(), ready() after them, missing(type) for a card no plugin draws and open(type, id, e) on a double-click.
//
// - Who registered what: each plugin gets its own view of HY (wrap) that notes its card kinds, its dock mode and the editor it puts in
//   the dock, so the board knows whose editor is open now.
// - On and off (Settings › Plugins, ui/plugins.js; the setting cv.plugoff): the server stops serving a plugin turned off at once
//   (review/plugins_admin.py); the board reloads without it, so its code goes with everything it added (its cards' editors, menu items,
//   dock mode, buttons). While the person is inside that plugin's editor the board waits, the plugin's row says «turns off when you leave
//   Dev mode», and the board holds the plugin on its server meanwhile (POST /api/plugins/hold, renewed while the editor is open), so the
//   editor keeps working; leaving it reloads the board. Turning one on, adding or removing one reloads the board the same way.
// - A card of a kind no loaded plugin draws (its plugin off or gone) stays in the board file as it is and shows its still picture with the
//   board's kind mark «Plugin off»: the picture the board last showed of that card (remembered per board), else the library's thumbnail
//   of its file (it.src or it.path), else a plain plate.
// - Hooks for plugins: HY.opener(type, fn) lets a plugin open another plugin's kind on a double-click (Dev studio opens the frames
//   plugin's HTML frames in Dev mode); fn(id, e) -> true when it took it. HY.ownOpen(id, dry) runs the card's own plugin's double-click
//   (an HTML frame's live view; dry: is there one), HY.claimed(type) says another plugin opens this kind. HY.changed(id): the file behind
//   a card changed elsewhere (Dev mode wrote an HTML frame's page), its own plugin draws it again (def.changed(id)).
(() => {
  if (window.hyPlugBoard) return;
  let HY = null, PLG = null, O = {}, READY = false, PEND = null, HELD = "", renew = 0;
  const T = (k, v) => (O.t ? O.t(k, v) : k), say = (m, k) => O.toast && O.toast(m, k);
  const OWN = { modes: {}, dock: "" };   // mode key -> {plugin, label}; the plugin whose editor is in the dock
  const OPEN = {}, LOADED = new Set();   // type -> [{fn, by}]; the plugins the server listed when the page loaded
  let ALL = null;   // GET /api/plugins/all: every plugin, on or off
  const store = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") || d; } catch { return d; } };
  const keep = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} };
  const KINDS = store("hy.plugkinds", {});   // card type -> {name, title} of the plugin that drew it
  const STILL = store("hy.plugstill", {});   // card id -> the address of the picture the board last showed in it
  let stillT = 0;
  const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b), keepalive: true }).catch(() => null);

  function init(hy, plg, o) {
    HY = hy; PLG = plg; O = o || {};
    hy.opener = (type, fn, by) => { if (typeof fn === "function") (OPEN[type] = OPEN[type] || []).push({ fn, by: by || "" }); };
    hy.claimed = type => !!(OPEN[type] && OPEN[type].length);
    hy.ownOpen = (id, dry) => {
      const it = HY.board.items[id], P = it && it.type && PLG[it.type];
      if (!P || P.standIn || !P.dblclick) return false;
      if (!dry) P.dblclick(id);
      return true;
    };
    hy.changed = id => { const it = HY.board.items[id], P = it && it.type && PLG[it.type]; try { if (P && P.changed) P.changed(id); } catch (e) { console.error(e); } };
    // the picture each plugin card shows, remembered for the day its plugin is off
    const items = document.getElementById("items");
    if (items) items.addEventListener("load", e => {
      const img = e.target, card = img.tagName === "IMG" && img.closest(".plg"); if (!card || card.classList.contains("plo")) return;
      try { const u = new URL(img.currentSrc || img.src, location.href); if (u.origin !== location.origin) return; STILL[card.dataset.id] = u.pathname + u.search; } catch { return; }
      clearTimeout(stillT); stillT = setTimeout(() => { const ks = Object.keys(STILL); ks.slice(0, Math.max(0, ks.length - 3000)).forEach(k => delete STILL[k]); keep("hy.plugstill", STILL); }, 1500);
    }, true);
    const prev = window.hyimgSettingsChanged;   // the app's settings came from elsewhere (Home, another board): cv.plugoff among them
    window.hyimgSettingsChanged = function () { const r = prev ? prev.apply(this, arguments) : undefined; apply(); return r; };
    window.hyimgPluginsChanged = () => { if (window.hyPlugins) window.hyPlugins.load(); apply(); };   // added or removed (the app)
    const dock = document.getElementById("dock");
    if (dock) new MutationObserver(() => check()).observe(dock, { attributes: true, subtree: true, attributeFilter: ["class", "aria-pressed"] });
  }

  // each plugin's own view of HY: what it registers is noted as its own
  function wrap(p) {
    LOADED.add(p.name);
    const H = Object.create(HY);
    H.register = (type, def) => { KINDS[type] = { name: p.name, title: p.title || p.name }; keep("hy.plugkinds", KINDS); return HY.register(type, def); };
    H.mode = (key, def) => { OWN.modes[key] = { plugin: p.name, label: (def && (def.name || def.label)) || "" }; return HY.mode(key, def); };
    H.dock = node => { if (node) OWN.dock = p.name; else if (OWN.dock === p.name) OWN.dock = ""; const r = HY.dock(node); check(); return r; };
    H.opener = (type, fn) => HY.opener(type, fn, p.name);
    return H;
  }
  function ready() {
    READY = true; HY.render();
    fetchAll().then(() => { document.querySelectorAll(".plg.plo").forEach(el => { el._k = ""; }); HY.render(); });   // «off» or «no plugin» now known
  }

  // a card no loaded plugin draws ---------------------------------------------------------------------------------------------------
  // the plugin that drew this kind last: off (still in the list, or the list not read yet) or gone
  const owner = type => { const k = KINDS[type]; return k ? { ...k, off: !ALL || !!ALL.find(p => p.name === k.name && !p.error) } : null; };
  function stillOf(it, id) {
    if (STILL[id]) return STILL[id];
    const p = typeof it.src === "string" ? it.src : typeof it.path === "string" ? it.path : "";
    return p ? `/thumb?p=${encodeURIComponent(p)}&s=640` : "";
  }
  const markHtml = text => `<span class="mk mk-br mk-kind" title="${text}"><b class="kp">${window.hyIcon ? window.hyIcon("plugin", 16, 2) : ""}</b>`
    + `<span class="kw"><span><span class="kt">${text}</span></span></span></span>`;
  const standIn = type => ({
    standIn: true, opacity: true,
    render(el, it, id) {
      const o = owner(type), word = o && o.off ? T("Plugin off") : T("No plugin");
      el.classList.add("plo");
      if (el._plo !== word) { el.innerHTML = `<img class="plo" alt="" decoding="async" draggable="false">` + markHtml(word); el._plo = word;
        el.firstChild.addEventListener("error", () => el.classList.add("plo-none")); }
      const img = el.firstChild, u = stillOf(it, id);
      if (img._u !== u) { img._u = u; el.classList.toggle("plo-none", !u); if (u) img.src = u; }
    },
    info(id, it) {
      const o = owner(type);
      return { name: o ? o.title : type, meta: o && o.off ? T("Plugin off") : T("No plugin"),
        text: o && o.off ? T("Turn it on in Settings › Plugins: the card stays as it was") : T("Its plugin is not installed: the card stays as it was") };
    },
    dblclick() {
      const o = owner(type);
      say(o && o.off ? T("{name} is off: turn it on in Settings › Plugins", { name: o.title }) : T("Its plugin is not installed: the card stays as it was"), "info");
    },
  });
  let again = 0;
  function missing(type) {
    if (!READY || !type || PLG[type]) return;
    PLG[type] = standIn(type);
    if (!again) again = requestAnimationFrame(() => { again = 0; HY.render(); });
  }

  // a double-click another plugin takes (HY.opener) -------------------------------------------------------------------------------
  function open(type, id, e) {
    if (PLG[type] && PLG[type].standIn) return false;
    for (const o of OPEN[type] || []) { try { if (o.fn(id, e)) return true; } catch (er) { console.error("plugin opener", er); } }
    return false;
  }

  // on and off -----------------------------------------------------------------------------------------------------------------------
  // whose editor is open: a plugin's mode in the dock's switch, or a plugin's own bar in the dock (an HTML frame's live view)
  function busy() {
    const m = window.MODES && window.MODES.open;
    if (m && m !== "board" && OWN.modes[m]) return { plugin: OWN.modes[m].plugin, label: OWN.modes[m].label };
    const d = document.getElementById("dock");
    if (OWN.dock && d && d.classList.contains("plg-mode")) return { plugin: OWN.dock, label: "" };
    return null;
  }
  async function fetchAll() {
    try { const d = await (await fetch("/api/plugins/all", { cache: "no-store" })).json(); ALL = d.plugins || []; if (window.hyPlugins) window.hyPlugins.got(d); }
    catch { /* the server is away for a moment: nothing changes */ }
    return ALL;
  }
  // the editor opened, changed or closed: the server holds that plugin while it is open; a change that waited goes in when it closes
  let ct = 0;
  function check() {
    if (ct) return;
    ct = requestAnimationFrame(async () => {
      ct = 0;
      const b = busy(), now = b ? b.plugin : "";
      if (now !== HELD) {
        if (HELD) await post("/api/plugins/hold", { name: HELD, on: false });
        HELD = now; clearInterval(renew);
        if (now) { post("/api/plugins/hold", { name: now, on: true }); renew = setInterval(() => post("/api/plugins/hold", { name: HELD, on: true }), 30000); }
      }
      if (PEND && !b) apply();
    });
  }
  let applying = null;
  function apply() {
    if (applying) return applying;
    return (applying = (async () => {
      try {
        if (!READY) return;
        const all = await fetchAll(); if (!all) return;
        const want = new Set(all.filter(p => !p.off && !p.error && p.canvas).map(p => p.name));   // a plugin with no canvas module is the server's alone
        const off = [...LOADED].filter(n => !want.has(n)), on = [...want].filter(n => !LOADED.has(n));
        PEND = off.length || on.length ? { off, on } : null;
        if (!PEND) { if (window.hyPlugins) window.hyPlugins.paint(); return; }
        if (busy()) { if (window.hyPlugins) window.hyPlugins.paint(); return; }   // waits: check() comes back here when the editor closes
        await reload();
      } finally { applying = null; }
    })());
  }
  // what a row says while its change waits for the studio to close (its full name: «Turns off when you leave Dev Studio»)
  function pending(name) {
    const b = PEND && busy(); if (!b) return "";
    const off = PEND.off.includes(name); if (!off && !PEND.on.includes(name)) return "";
    if (b.label) return off ? T("Turns off when you leave {mode}", { mode: b.label }) : T("Turns on when you leave {mode}", { mode: b.label });
    return off ? T("Turns off when you leave the studio") : T("Turns on when you leave the studio");
  }
  // the board again, with the plugins as they are now: saved first; the settings panel opens again where it was
  async function reload() {
    let n = []; try { n = JSON.parse(sessionStorage.getItem("hy.plugReload") || "[]").filter(t => Date.now() - t < 20000); } catch {}
    if (n.length >= 3) { say(T("The board reloaded for its plugins 3 times in a row: stopped"), "error"); return; }
    try { sessionStorage.setItem("hy.plugReload", JSON.stringify([...n, Date.now()])); } catch {}
    if (O.save && O.saved && !O.saved()) { O.save(); for (let i = 0; i < 40 && !O.saved(); i++) await new Promise(r => setTimeout(r, 100)); }
    if (HELD) { await post("/api/plugins/hold", { name: HELD, on: false }); HELD = ""; }
    try { if (document.getElementById("sets") && document.getElementById("sets").classList.contains("open")) sessionStorage.setItem("hy.setsOpen", "1"); } catch {}
    location.reload();
  }

  // isReady: ready() ran, the plugins are in and their cards drawn (ui/switchin.js waits for it before a switched-to board comes in)
  window.hyPlugBoard = { init, wrap, ready, missing, open, apply, pending, busy, get loaded() { return [...LOADED]; }, get isReady() { return READY; } };
})();
