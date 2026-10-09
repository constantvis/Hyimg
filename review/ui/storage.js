// Settings › Storage (owner 2026-10-07: «show in Settings the cache size and how much each project takes, also on Home, and how
// much RAM the app uses right now»; «мне гораздо важнее, чтобы было свободнее на диске»). A section at the end of the settings
// panel, the same on Home and on a board: the boards' folders, what Hyimg made in them, its cache with «Clear cache», the app's old copies, the
// duplicates and the memory of the app's processes now. Home also shows each board's size and sorts by it (hyStore.size, .sort).
//
// Where the numbers come from: review/storage.py measures in its own low-priority process and keeps the last result; nothing here
// waits for a scan. A board's page asks its server (GET /api/storage), Home asks the app ({action: "storage", op: "summary"}), the
// memory always comes from the app (op "ram", native/Storage.swift); a page in a plain browser shows its server's memory only.
// Deleting is two buttons, each asked first: «Clear cache» (only what Hyimg makes again, inside its cache folder, storage_clean.py)
// and the app's old copies into the Trash.
(() => {
  if (window.hyStore) return;
  const SRC = (document.currentScript && document.currentScript.src) || location.href;
  const FILE = location.protocol === "file:";
  const wk = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.hyimg;
  const cef = /HyimgCEF/.test(navigator.userAgent);
  const toApp = m => { if (wk) { wk.postMessage(m); return true; } if (cef) { console.log("HYIMG_MSG:" + JSON.stringify(m)); return true; } return false; };
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const T = window.T || (s => s);
  // where the settings' sections stand: the settings window's body (ui/settings-win.js, hySetPanel.body()), else the page's #sets
  const host = () => (window.hySetPanel && window.hySetPanel.body()) || document.getElementById("sets");
  const S = { sum: null, age: null, scanning: false, ram: null, server: null, busy: "", t: 0, lost: [] };
  const css = document.createElement("link"); css.rel = "stylesheet"; css.href = new URL("storage.css", SRC).href; document.head.appendChild(css);

  // 1.2 GB, 580 MB, 12 KB: digits in the language's grouping, decimal units like Finder
  function fmt(b) {
    b = Number(b) || 0;
    const [n, u] = b >= 1e9 ? [b / 1e9, "GB"] : b >= 1e6 ? [b / 1e6, "MB"] : [b / 1e3, "KB"];
    const v = { n: n.toLocaleString(T.locale || undefined, { maximumFractionDigits: n < 10 ? 1 : 0 }) };
    return u === "GB" ? T("{n} GB", v) : u === "MB" ? T("{n} MB", v) : T("{n} KB", v);
  }
  const disk = o => (o && (o.disk ?? o.bytes)) || 0;
  // «Server 4180 · 3 h» | «Blender · 40 min» | «qlmanage · 27 h»: what it is, how long it has been running
  const lostName = p => (p.kind === "blender" ? "Blender" : p.kind === "helper" ? String(p.port || "helper")
    : p.port ? T("Server {port}", { port: String(p.port) }) : T("Server"))
    + " · " + (p.age >= 3600 ? T("{n} h", { n: Math.round(p.age / 3600) }) : T("{n} min", { n: Math.max(1, Math.round(p.age / 60)) }));

  function got(d) {
    if (!d) return;
    S.sum = d.summary || S.sum; S.age = d.age; S.scanning = !!d.scanning; S.t = Date.now(); S.lost = d.lost || []; S.caps = d.caps || S.caps;
    if (d.server) S.server = d.server;
    if (d.perflog) S.perf = d.perflog;   // the performance log's files (review/perflog.py): a board's server, on Home the app's storage.py summary
    paint();
    if (typeof window.render === "function" && FILE) window.render();   // Home: the sizes on the boards
    clearTimeout(S.again); if (S.scanning || !S.sum) S.again = setTimeout(load, 15000);   // a scan runs behind: its result in a moment
  }
  function load() {
    if (FILE) { toApp({ action: "storage", op: "summary" }); return; }
    fetch("/api/storage", { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(got).catch(() => {});
  }
  function ram() { if (!toApp({ action: "storage", op: "ram" })) paint(); }
  window.hyimgStorage = d => {
    if (!d) return;
    if (d.op === "ram") { S.ram = d; paint(); return; }
    if (d.op === "summary") { got(d); return; }
    if (d.op === "caps") { if (d.caps) { S.caps = d.caps; paint(); } return; }
    finished(d);
  };

  // what the person sees ------------------------------------------------------------------------------------------------------------
  const KINDS = [["gpu", "Graphics"], ["pages", "Pages"], ["servers", "Servers"], ["app", "Window"], ["services", "Services"],
    ["blender", "Blender"], ["scan", "Scan"], ["other", "Other"]];
  const row = (label, value, extra = "", cls = "") => `<div class="hs-row ${cls}"><span>${label}</span><b>${value}</b>${extra}</div>`;
  const btn = (act, words, dis, more = "") => `<hy-button size="s" data-hs="${act}"${more}${dis ? " disabled" : ""}>`
    + (UPGRADED() ? esc(words) : `<button type="button"${dis ? " disabled" : ""}>${esc(words)}</button>`) + "</hy-button>";
  // the thumbnail cache's ceiling (review/thumbcache.py): the oldest used go first above it; a choice as the panel's others (ui/setpanel.js,
  // <hy-segmented variant=well>), its chosen option marked here too for Home, where the element is not upgraded
  const capRow = (k, label, opts) => `<div class="hs-row hs-sub hs-cap"><span>${label}</span><hy-segmented class="seg" variant="well" data-hscap="${k}" `
    + `value="${Number(S.caps[k])}" role="radiogroup" aria-label="${esc(label)}">` + opts.map(v => { const on = Number(S.caps[k]) === v;
      return `<button type="button" value="${v}" data-cap="${v}" class="${on ? "on" : ""}" role="radio" aria-checked="${on}" tabindex="${on ? 0 : -1}">${T("{n} GB", { n: v })}</button>`; }).join("")
    + "</hy-segmented></div>";
  const info = tip => ` <span class="hy-info" role="img" title="${esc(tip)}"></span>`;
  // a board's page upgrades <hy-button> (ui/hy/index.js); Home links its CSS only, so the real button is written here
  const UPGRADED = () => !!(window.customElements && customElements.get("hy-button"));

  function section() {
    let el = document.getElementById("hyStore");
    const sets = host();
    if (!el && sets) {
      el = document.createElement("section"); el.id = "hyStore"; el.className = "hs"; el.setAttribute("aria-label", T("Storage"));
      sets.appendChild(el);
      // an upgraded <hy-segmented> (a board) says hy-change, also for the arrow keys; on Home the click is the choice
      const upgraded = s => !!(window.customElements && customElements.get("hy-segmented") && s.matches(":defined"));
      el.addEventListener("hy-change", e => { const s = e.target.closest("[data-hscap]"); if (s) setCap(s.dataset.hscap, +e.detail.value); });
      el.addEventListener("click", e => {
        const c = e.target.closest("[data-cap]");
        if (c) { e.stopPropagation(); if (!upgraded(c.closest("[data-hscap]"))) setCap(c.closest("[data-hscap]").dataset.hscap, +c.dataset.cap); }
      });
      el.addEventListener("click", e => { const b = e.target.closest("[data-hs]"); if (b && !b.hasAttribute("disabled")) act(b.dataset.hs, b.dataset.pid); });
    }
    return el;
  }
  function paint() {
    const el = section(); if (!el) return;
    const s = S.sum, tt = s && s.totals, g = s && s.global;
    const age = S.scanning ? T("Measuring…") : S.age != null ? T.ago ? T.ago(Date.now() - S.age * 1000) : "" : "";
    let h = `<div class="sh"><span class="hs-t">${T("Storage")}</span><span>${esc(age)}</span></div>`;
    if (!s) h += `<div class="hs-row"><span>${S.scanning || S.t === 0 ? T("Measuring the folders…") : T("Not measured yet")}</span></div>`;
    else {
      const boards = (s.boards || []).filter(b => b.total).sort((a, b) => disk(b.total) - disk(a.total));
      h += row(T("Boards"), fmt(disk(tt.boards)));
      h += `<div class="hs-list">${boards.map(b => row(esc(b.name), fmt(disk(b.total)), "", "hs-sub")).join("")}</div>`;
      h += row(T("Made by Hyimg") + info(T("Thumbnails, previews and stills in the boards' folders: Hyimg draws them again")), fmt(disk(tt.made)));
      const clear = disk(tt.clearable);
      h += row(T("Cache"), fmt(disk(tt.cache)), btn("clear", clear ? T("Clear {size}", { size: fmt(clear) }) : T("Nothing to clear"), !clear || S.busy));
      if (S.caps) h += capRow("board", T("Thumbnails per board"), [1, 2, 5]) + capRow("total", T("Thumbnails in all"), [4, 8, 16]);
      const n = (g.backups || []).length;
      if (n) h += row(T("App copies · {n}", { n }), fmt(disk(tt.backups)), n > 2 ? btn("backups", T("To the Trash"), !!S.busy) : "");
      if (tt.dups) h += row(T("Duplicates") + info(T("Identical files in a board's folder: the space the extra copies take")), fmt(tt.dups));
    }
    // the log of frame drops (Settings › Diagnostics, review/perflog.py): its size and «Clear», asked first. A board clears it through
    // its server (POST /api/perflog/clear), Home through the app (op "perflog": native/StorageBridge.swift runs perflog.py clear)
    if (S.perf) h += row(T("Performance log") + info(T("Frame drops with what was on screen, written only while the log is on (Settings › Diagnostics)")),
      fmt(S.perf.bytes), btn("perflog", T("Clear"), !S.perf.bytes || !!S.busy));
    const r = S.ram;
    if (r && r.total) {
      h += row(T("Memory now"), fmt(r.total));
      const parts = KINDS.filter(([k]) => r.kinds && r.kinds[k]).map(([k, w]) => `<span>${T(w)} <b>${fmt(r.kinds[k])}</b></span>`);
      h += `<div class="hs-row hs-sub hs-kinds">${parts.join("")}</div>`;
    } else if (S.server && S.server.bytes) h += row(T("Server memory"), fmt(S.server.bytes));
    // servers and Blender whose parent is gone (review/procs.py): each with its memory and «Stop», asked first
    const lost = S.lost || [];
    if (lost.length) {
      h += row(T("Lost processes · {n}", { n: lost.length }) + info(T("Hyimg servers, Blender and their helpers left running by a test or an agent that ended")),
        fmt(lost.reduce((a, p) => a + (p.bytes || 0), 0)));
      const stop = p => btn("stop", T("Stop"), !!S.busy, ` data-pid="${p.pid}"`);
      h += `<div class="hs-list">${lost.map(p => row(esc(lostName(p)), fmt(p.bytes), stop(p), "hs-sub")).join("")}</div>`;
    }
    h += `<div class="hy-hint">${T("«Clear» removes <b>only Hyimg's own cache</b>, never your files")}</div>`;
    if (el._h !== h) { el.innerHTML = h; el._h = h; if (window.hySeg) window.hySeg(el); }
  }

  // the ceiling, set at once: Home through the app, a board through its server; every server reads it before its next round
  function setCap(k, v) {
    S.caps = { ...(S.caps || {}), [k]: v }; paint();
    if (FILE) { toApp({ action: "storage", op: "caps", [k]: v }); return; }
    fetch("/api/storage/caps", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [k]: v }) }).catch(() => {});
  }

  // the two deletions: asked first, then a notification of what was freed ----------------------------------------------------------
  async function ask(o) {
    if (!window.hyConfirm && !FILE) { try { await import(new URL("confirm.js", SRC).href); } catch {} }
    if (window.hyConfirm) return new Promise(ok => window.hyConfirm({ ...o, icon: "trash", onOk: () => ok(true), onCancel: () => ok(false) }));
    return null;   // Home: the app asks with its own dialog
  }
  async function act(what, pid) {
    if (S.busy) return;
    const tt = (S.sum && S.sum.totals) || {}, n = ((S.sum && S.sum.global && S.sum.global.backups) || []).length;
    const p = what === "stop" && (S.lost || []).find(x => String(x.pid) === String(pid));
    if (what === "stop" && !p) return;
    const o = p ? { title: T("Stop {name}?", { name: lostName(p) }), ok: T("Stop"), cancel: T("Cancel"),
        note: T("It frees {size}. The app's own servers are not touched", { size: fmt(p.bytes) }) }
      : what === "perflog" ? { title: T("Clear the performance log, {size}?", { size: fmt((S.perf || {}).bytes) }), ok: T("Clear"), cancel: T("Cancel"),
          note: T("Only the log of frame drops in the app's cache") }
      : what === "clear"
      ? { title: T("Clear the cache, {size}?", { size: fmt(disk(tt.clearable)) }), ok: T("Clear"), cancel: T("Cancel"),
          note: T("Video copies, 3D conversions and folders of removed boards. Hyimg makes them again when needed") }
      : { title: T("Move {n} old app copies to the Trash?", { n: Math.max(0, n - 2) }), ok: T("To the Trash"), cancel: T("Cancel"),
          note: T("The 2 newest stay. They can be put back from the Trash") };
    const yes = await ask(o);
    if (yes === false) return;
    S.busy = what; paint();
    if (yes === null) { if (!toApp({ action: "storage", op: what, confirm: true, pid: p ? p.pid : undefined, ...o })) { S.busy = ""; paint(); } return; }
    if (FILE) { toApp({ action: "storage", op: what, pid: p ? p.pid : undefined }); return; }
    const body = what === "clear" ? {} : what === "stop" ? { pid: p.pid } : { keep: 2 };
    const res = await fetch(what === "perflog" ? "/api/perflog/clear" : "/api/storage/" + what, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(r => r.json()).catch(() => ({ error: "network" }));
    finished({ op: what, ...res });
  }
  function finished(d) {
    S.busy = "";
    if (d.cancelled) { paint(); return; }
    const say = window.hyToast || (() => {});
    if (d.error) say(d.op === "stop" ? T("Not stopped: {why}", { why: d.error }) : T("Nothing was deleted: {why}", { why: d.error }), "error");
    else if (d.op === "stop") { S.lost = (S.lost || []).filter(x => x.pid !== d.stopped); say(T("Stopped, {size} freed", { size: fmt(d.freed) }), "success"); }
    else if (d.op === "clear" || d.op === "perflog") { if (d.op === "perflog") S.perf = { bytes: 0, files: 0 }; say(T("Freed {size}", { size: fmt(d.freed) }), "success"); }
    else say(T("{n} copies in the Trash, {size} freed", { n: (d.trashed || []).length, size: fmt(d.freed) }), "success");
    paint(); setTimeout(load, 1500);   // the scan the deletion started
  }

  // the panel: measured when it opens, the memory every 2 s while it is open ----------------------------------------------------------
  let timer = 0;
  function watch() {
    const sets = document.getElementById("sets"); if (!sets) return;
    const on = () => sets.classList.contains("open");
    new MutationObserver(() => {
      if (on() && !timer) { paint(); load(); ram(); timer = setInterval(ram, 2000); }
      else if (!on() && timer) { clearInterval(timer); timer = 0; }
    }).observe(sets, { attributes: true, attributeFilter: ["class"] });
    if (FILE) load();   // Home: the boards' sizes without opening the panel
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch); else watch();

  // Home: a board's size on its card and in the list, sorted by size when asked (home.json sort: "size") --------------------------
  const bytesOf = p => {
    const b = S.sum && (S.sum.boards || []).find(x => String(x.id).toUpperCase() === String(p.id).toUpperCase());
    return b && b.total ? disk(b.total) : null;
  };
  window.hyStore = {
    fmt, load,
    size: p => { const b = bytesOf(p); return b == null ? "" : fmt(b); },
    sizeCell: p => { const b = bytesOf(p); return `<div class="c4">${b == null ? "" : esc(fmt(b))}</div>`; },
    sort: (list, key) => key === "size" ? [...list].sort((a, b) => (bytesOf(b) ?? -1) - (bytesOf(a) ?? -1)) : list,
    th: key => `<button class="hs-th" data-sort="size" aria-pressed="${key === "size"}" title="${esc(T("Sort by size"))}">${T("Size")}</button>`,
  };
  document.addEventListener("click", e => {   // the list's «Size» heading: the biggest first, again for the order before
    const b = e.target.closest(".hs-th[data-sort]"); if (!b || typeof window.render !== "function" || typeof HOME !== "object") return;
    HOME.sort = HOME.sort === "size" ? undefined : "size";
    if (typeof saveHome === "function") saveHome();
    window.render();
  });
})();
